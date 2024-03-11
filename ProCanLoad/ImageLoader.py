import os
import pandas as pd
import numpy as np
import SimpleITK as sitk
from collections import OrderedDict
from pathlib import Path
from tqdm.auto import tqdm
import copy

from .SegmentationLoader import SegmentationLoader
from .utils import DataFrameUtils, JsonUtils
from .utils import GetDirectionDict
from .pydicom_utils import DCMUtils
from .sitk_utils import SitkUtils
from .IssueLogger import IssueLogger
from typing import Union


class ImageLoader:

    def __init__(self,  images_directory_path: Path,
                        parquet_series: Union[Path, pd.DataFrame],
                        parquet_segmentations: Union[Path, pd.DataFrame] = None,
                        add_columns: Union[list, str] = None,
                        reset_logger: bool = True,
                        extract_nii: bool = False
    ) -> None:
        
        self.images_directory_path = images_directory_path
        self.parquet_series = parquet_series
        self.parquet_segmentations = parquet_segmentations
        self.add_columns = add_columns
        self.extract_nii = extract_nii
        

        self.default_cols = [
                                'provided_by',
                                'patient_id', 
                                'study_uid', 
                                'series_uid', 
                                'user_series_type',
                                'catboost_series_type_heuristics',
                                'series_description', 
                                'diffusion_bvalue',
                                'manufacturer',
                                'manufacturer_model_name',
                                'use_case_form'
        ]
        
        self.logger = IssueLogger(reset = reset_logger)

        
#%% parquet related process

    def PrintDefaultColumns(self):
        '''
        Prints default columns that must exist in the parquet file
        '''
        for col in self.default_cols:

            print(col)

    def LoadParquet(self):
        '''
        Load parquet file and drop columns not inside the default or selected columns.
        Wrong inputs will be ignored.
        '''
        select_columns = []
        
        if self.add_columns != None:

            if isinstance(self.add_columns,str):

                select_columns = [col.strip() for col in self.add_columns.split(',') 
                                  if col not in self.default_cols]

            elif isinstance(self.add_columns,list):
                
                select_columns = [col for col in self.add_columns
                                  if col not in self.default_cols]

            else:

                
                print('If you meant to select more columns from the parquet file, \n \
                      you should give the column names as a string with comma as delimeter or a list. \n \
                      Proceeding with the default columns\n')
                
                print(f'Default columns:')

                self.PrintDefaultColumns()

                self.logger.LogIssue( 'select_col', {'bad_format':'Use strings with "," delimeter or list'} )
        

        self.df = DataFrameUtils.Read(self.parquet_series)

        self.selected_columns = [col for col in self.default_cols if col in self.df]

        for col in self.default_cols:

                if col not in self.df.columns:

                    print(f'Default column named "{col}" does not exist inside parquet file and it will be ignored')

                    self.logger.LogIssue( 'default_col', {col:'does not exist'} )

        for col in select_columns:

            if col not in self.df.columns:

                print(f'"{col}" does not exist inside parquet file and it will be ignored')

                self.logger.LogIssue( 'select_col', {col:'does not exist'} )

            else:

                self.selected_columns.append(col)

        self.df = self.df[self.selected_columns].copy()
        
        if isinstance(self.parquet_segmentations, pd.DataFrame):
            pass
        elif self.parquet_segmentations != None:
            self.seg_df = DataFrameUtils.Read(self.parquet_segmentations)
            
        return self.df
    
    def __CheckPathExist(self) -> bool:
        
        path_exists = os.path.exists(self.series_path)

        if not path_exists:
            self.logger.LogIssue('FileNotFound',{self.series_path:'Not found'})

        return path_exists
    
    def __CheckDuplicate(self, imageA:Path, imageB:Path)->bool:
        '''
        Checks if the images with same slice location and same bvalue ('N/A' if not DWI) are the same
        '''

        A = SitkUtils.LoadSingleFile(imageA)
        A = sitk.GetArrayFromImage(A)

        B = SitkUtils.LoadSingleFile(imageB)
        B = sitk.GetArrayFromImage(B)

        return np.array_equal(A, B)
    
    def GetMetaData(self, data: pd.DataFrame) -> dict:


                temp_meta = {'meta': 
                                    {   
                                        'series_uid': self.series_uid,
                                        'study_uid': self.study_uid,
                                        'provided_by': data.provided_by.values[0],
                                        'user_series_type': data.user_series_type.values[0],
                                        'catboost_series_type_heuristics': data.catboost_series_type_heuristics.values[0],
                                        'series_description': data.series_description.values[0],
                                        'manufacturer': data.manufacturer.values[0],
                                        'manufacturer_model_name': data.manufacturer_model_name.values[0],
                                        'use_case_form': data.use_case_form.values[0],
                                        'diffusion_bvalue': data.diffusion_bvalue.values[0]
                                    }
                }
                
                if len(self.selected_columns) > len(self.default_cols):
                    for col in self.selected_columns:
                        if col not in self.default_cols:
                            temp_meta['meta'][col] = data[col].values[0]

                return temp_meta
    
    def __GetPatientsWithOnlyUnknown(self) -> list:

        unkwnown_dwi_pat = []
        
        for patient,pval in self.image_loader.items():

            for study,stval in pval.items():

                if 'DWI' not in stval:
                    continue
                
                if len(stval['DWI'].keys() ) == 1:
                    continue

                bval_keys = list(stval['DWI'].keys())

                count_unknown = 0

                for bval_key in bval_keys:
                    if 'Unknown' in str(bval_key):
                        count_unknown += 1

                if (count_unknown <= 1) or (len( set ( bval_keys ) ) != count_unknown):
                    continue

                unkwnown_dwi_pat.append(patient)

        return unkwnown_dwi_pat

    
    def __OrderMultipleUnknownDWISeries(self):

        unkwnown_dwi = self.__GetPatientsWithOnlyUnknown()
        self.AvoidDWI = {}

        orderbymax_meanvalue_dict = {}
        for patient in unkwnown_dwi:

            orderbymax_meanvalue_dict[patient] = {}

            for study,stval in self.image_loader[patient].items():

                if 'DWI' not in stval:
                    continue
        
                orderbymax_meanvalue_dict[patient][study] = {}

                unknown_keys = list( stval['DWI'].keys() )
                pos_keys = list ( stval['DWI'][unknown_keys[0]]['dcm_path'].keys() )

                slice_len = 0
    
                for b in unknown_keys:

                    N_image_size = len( self.image_loader[patient][study]['DWI'][b]['dcm_path'].keys() )

                    if N_image_size > slice_len:
                        slice_len = N_image_size
                
                temp_unknown_keys = [b for b in unknown_keys if  len( self.image_loader[patient][study]['DWI'][b]['dcm_path'].keys()) == slice_len]

                for b in unknown_keys:

                    if b not in temp_unknown_keys:
                        self.logger.LogIssue('DWIMultiSeriesNotSameSliceNumber',{ f'{patient}_{study}_{unknownkey}': len( self.image_loader[patient][study]['DWI'][unknownkey]['dcm_path'].keys())
                                                                        for unknownkey in unknown_keys
                                                                        }
                        )

                        self.AvoidDWI.update({patient:{study:b}})

                unknown_keys = temp_unknown_keys

                for pos in pos_keys:

                    orderbymax_meanvalue_dict[patient][study][pos] = {}

                    for unknownB in unknown_keys:

                        temp_path = stval['DWI'][unknownB]['dcm_path'][pos]['path']
                        temp_img = sitk.ReadImage(temp_path)
                        temp_max = sitk.GetArrayFromImage(temp_img).max()
                        temp_mean = sitk.GetArrayFromImage(temp_img).mean()
                        
                        orderbymax_meanvalue_dict[patient][study][pos][f"{temp_max}_{temp_mean}"] = temp_path

                    orderbymax_meanvalue_dict[patient][study][pos] = OrderedDict(   sorted (orderbymax_meanvalue_dict [patient][study][pos].items(), 
                                                                                    key=lambda x: (float(x[0].split('_')[0]), float(x[0].split('_')[1])), 
                                                                                    reverse=True)
                    )


    
        for patient in unkwnown_dwi:

            for study,stval in self.image_loader[patient].items():

                if 'DWI' not in stval:
                    continue

                unknown_keys = list( stval['DWI'].keys() )
                pos_keys = list ( stval['DWI'][unknown_keys[0]]['dcm_path'].keys() )

                slice_len = 0

                for b in unknown_keys:

                    N_image_size = len( self.image_loader[patient][study]['DWI'][b]['dcm_path'].keys() )

                    if N_image_size > slice_len:
                        slice_len = N_image_size
                
                unknown_keys = [b for b in unknown_keys if  len( self.image_loader[patient][study]['DWI'][b]['dcm_path'].keys()) == slice_len]


                for pos in pos_keys:

                    max_values = list ( orderbymax_meanvalue_dict[patient][study][pos].keys() )

                    for i,unknownB in enumerate(unknown_keys):
                        self.image_loader[patient][study]['DWI'][unknownB]['dcm_path'][pos]['path'] = orderbymax_meanvalue_dict[patient][study][pos][max_values[i]]
                        self.image_loader[patient][study]['DWI'][unknownB]['dcm_path'][pos]['max_mean'] = max_values[i]


    def OrderFileSeries(self, series_files:tuple):

        if not hasattr(self,'df'):
            self.LoadParquet()

        mask_df =   (self.df.patient_id == self.patient_id) & \
                    (self.df.study_uid  == self.study_uid) & \
                    (self.df.series_uid == self.series_uid)
        
        df_series = self.df[mask_df].copy()

        sequence = df_series.user_series_type.values[0]
        
        df_bvalue = df_series.diffusion_bvalue.values[0]

        if sequence == 'T2AX':
            sequence = 'T2'

        if not sequence:
            sequence = df_series.catboost_series_type_heuristics.values[0]

        self.sequence = sequence

        meta = self.GetMetaData(df_series)

        location_dict = {}
        bvalue_list = []
        original_bvalue = []
        plane_found = []
        duplicates_found = []
        direction_dict = GetDirectionDict()
        rescale_type = None

        for file in series_files:

            file = file.replace('\\','/')
            
            #Pydicom is used for bvalues at this point. Sitk does not decode the b-values and in some cases return None for unreadable tags
            dcm_img = DCMUtils.ReadSlice(file)
            sitk_img = SitkUtils.ReadImageInfo(file)

            plane = SitkUtils.GetImagePlane(sitk_img)

            origin_idx = direction_dict[plane]['origin']
            plane_name = direction_dict[plane]['plane']

            if plane_name not in plane_found:
                plane_found.append(plane_name)



            origin = sitk_img.GetOrigin()

            bvalue = 'N/A'

            if sequence != 'DWI':

                if bvalue not in location_dict:
                    
                    location_dict[bvalue] = {
                                                'origin': [],
                                                'main_plane_origin': [],
                                                'path': []                            
                }
                    
                if origin in location_dict[bvalue]['origin']:

                    same_origin = location_dict[bvalue]['origin'].index(origin)
                    comparison_image_path = location_dict[bvalue]['path'][same_origin]

                    if self.__CheckDuplicate(file, comparison_image_path):
                        duplicates_found.append(file)
                        self.logger.LogIssue( 'DuplicateDetected', { self.series_uid: duplicates_found} )
                        continue
                    
                    else:

                        self.logger.LogIssue( 'SameOriginFound', { self.series_uid: 'No Duplicate Image'} )
                        continue


                location_dict[bvalue]['origin'].append(origin)
                location_dict[bvalue]['main_plane_origin'].append(origin[origin_idx])
                location_dict[bvalue]['path'].append(file)

                if sequence == 'ADC' and (0x0028,0x1054) in dcm_img:

                    rescale_type = dcm_img[(0x0028,0x1054)].value



            if sequence == 'DWI':
                self.check = dcm_img
                bvalue, message = DCMUtils.GetBValue(dcm_img)
                sitk_bvalue = SitkUtils.GetBvalue(sitk_img)

                if bvalue == None:
                    
                    self.logger.LogIssue('MissingBValue',{self.series_uid:f'{message} and {df_bvalue} in parquet'})
                    bvalue = 'Unknown'

                if bvalue not in location_dict:
                    
                    location_dict[bvalue] = {
                                                'origin': [],
                                                'main_plane_origin': [],
                                                'path': []                            
                }
                
                if bvalue in location_dict:
                    
                    counter = 0
                    no_duplicated = True

                    while (origin in location_dict[bvalue]['origin']) and no_duplicated :

                        base = bvalue.split('-')[0]
                        same_origin = location_dict[bvalue]['origin'].index(origin)
                        comparison_image_path = location_dict[bvalue]['path'][same_origin]
                        counter += 1
                        bvalue = base+f'-{counter}'

                        if self.__CheckDuplicate(file, comparison_image_path):

                            no_duplicated = False
                            duplicates_found.append(file)
                            self.logger.LogIssue( 'DuplicateDetected', { self.series_uid: duplicates_found} )
                            bvalue = bvalue.split('-')[0]

                            continue

                        if bvalue not in location_dict:
                    
                            location_dict[bvalue] = {
                                                        'origin': [],
                                                        'main_plane_origin': [],
                                                        'path': []                            
                            }

                if bvalue not in bvalue_list:
                    bvalue_list.append(bvalue)

                if sitk_bvalue not in original_bvalue:
                    original_bvalue.append(sitk_bvalue)


                location_dict[bvalue]['origin'].append(origin)
                location_dict[bvalue]['main_plane_origin'].append(origin[origin_idx])
                location_dict[bvalue]['path'].append(file)



                meta['meta']['Non Decoded sitk Bvalues'] = ','.join( map(str,original_bvalue) )
                meta['meta']['Decoded Pydicom Bvalues'] = ','.join( map(str, bvalue_list) )
                            
        if len(plane_found) > 1:

            self.logger.LogIssue('MultiplePlanesFound',{self.series_uid:plane_found})
            meta['meta']['Image Main Plane'] = ','.join( map(str,plane_found))

        elif len(plane_found) == 1:

            meta['meta']['Image Main Plane'] = plane_found[0]

        if rescale_type:
            meta['meta']['rescale_type'] = rescale_type


        if sequence in self.image_loader[self.patient_id][self.study_uid]:
            base_seq = sequence.split('-')[0]
            c = 0
            while sequence in self.image_loader[self.patient_id][self.study_uid]:
                c += 1
                sequence = base_seq+f'-{c}'

        if sequence not in self.image_loader[self.patient_id][self.study_uid]:
            self.image_loader[self.patient_id][self.study_uid][sequence] = {}
        

        for bv in location_dict:

            self.image_loader[self.patient_id][self.study_uid][sequence][bv] = copy.deepcopy(meta)

            origin_list = location_dict[bv]['origin'].copy()
            main_origin_list = location_dict[bv]['main_plane_origin'].copy()
            path_list = location_dict[bv]['path'].copy()

            dcm_path = {main_or:
                                {
                                    'path':pth,
                                    'ImagePositionPatient': ','.join( map(str, orig) )
                                }
                for main_or,pth,orig in zip(main_origin_list,path_list,origin_list)
            }




            dcm_path = OrderedDict(sorted(dcm_path.items()))
            self.image_loader[self.patient_id][self.study_uid][sequence][bv]['dcm_path'] = copy.deepcopy(dcm_path)

            #If segmentation for parquet is given
            if isinstance(self.parquet_segmentations,str):
                self.df_seg = DataFrameUtils.Read(self.parquet_segmentations)

                if self.sequence == 'T2':
                    
                    load_segs = SegmentationLoader(self.images_directory_path,self.parquet_series,self.parquet_segmentations)

                    if self.series_uid in self.df_seg.source_series_uid.to_list():

                        label_dict, zeromask_dict = load_segs.GetSeriesSegmentations( self.image_loader[self.patient_id][self.study_uid][sequence]['N/A'] )

                        self.image_loader[self.patient_id][self.study_uid]['SEG'] = label_dict

                        if zeromask_dict:

                            for label in zeromask_dict:
                                self.logger.LogIssue("ZeroMaskFound",{zeromask_dict[label]['meta']['seg_series_uid']:f"Mask {label} derived from{self.series_uid}, patient {self.patient_id}"})


    def GetImageLoader(self) -> dict:
        
        self.LoadParquet()

        self.pat_dict = {
                        patient: {
                                    study: self.df[(self.df.patient_id == patient) & (self.df.study_uid == study)].series_uid.tolist()
                                    for study in self.df[self.df.patient_id == patient].study_uid.unique()
                                }
                                for patient in self.df.patient_id.unique()
        }
        self.image_loader = {}
        for patient in tqdm(self.pat_dict, desc= 'Reading ... ', colour='MAGENTA'):

            self.image_loader[patient] = {}
            self.patient_id = patient

            for study in self.pat_dict[patient]:

                self.study_uid = study
                self.image_loader[patient][study] = {}

                for series in self.pat_dict[patient][study]:
                    
                    self.series_uid = series
                    self.series_path = os.path.join(self.images_directory_path,patient,study,series).replace('\\','/')
                    
                    if not self.__CheckPathExist():
                        continue
                    
                    #Load files' path contained in series_path
                    files = SitkUtils.GetFiles(self.series_path)

                    self.OrderFileSeries(files)

        self.__OrderMultipleUnknownDWISeries()

        JsonUtils.Write(self.image_loader, 'image_loader.json')

        if self.extract_nii:

            extractor = DICOM2NII('image_loader.json',
                                    keep_max_bvalue= True,
            )

            extractor.Execute()

        


class DICOM2NII():
        
    def __init__(self, 
                    image_loader: Union[str, dict],
                    keep_max_bvalue:bool = True,
    ) -> None:
        
        self.image_loader = image_loader
        
        if isinstance(image_loader, str):
            self.image_loader = JsonUtils.Load(image_loader)
        
        self.keep_max_bvalue = keep_max_bvalue
        self.logger = IssueLogger(reset = False)
        
    def ADCMicro2Nano(self, ADCITK: sitk.Image):

        ADC_np = sitk.GetArrayFromImage(ADCITK).max()
        
        if ADC_np <= 10:

            return ADCITK * 1000
        
        return ADCITK

    def __LoadDWIMultiSeriesWithMissingSlice(self):

        check_issues = JsonUtils.Load('issues/image_loader_issues.json')
        exclude_dict = {}

        if "DWIMultiSeriesNotSameSliceNumber" in check_issues:
            check_issues = check_issues["DWIMultiSeriesNotSameSliceNumber"]
            
            #Remove Unknown with smaller number of slices
            if check_issues:

                for bkey, value in check_issues.items():

                    pat, stu, bunknown = bkey.split('_')

                    if pat not in exclude_dict:
                        
                        exclude_dict[pat] = {}

                    if stu not in exclude_dict[pat]:
                    
                        exclude_dict[pat][stu] = {}

                    if value not in exclude_dict[pat]:
                    
                        exclude_dict[pat][stu][value] = bunknown
                    
                    exclude_dict[pat][stu][value] = bunknown

                temp = exclude_dict.copy()
                for pat, value in temp.items():

                    for stu, svalue in value.items():

                        key = max( list( svalue.keys() ) )

                        exclude_dict[pat][stu] = temp[pat][stu][key]

        self.exclude_dict = exclude_dict
            
    def Execute(self) -> dict:

        extract_folder = 'nii_files'

        nii_dict = {}
        self.missing_seg_list = []
        self.largest_bvalue = {}
        self.__LoadDWIMultiSeriesWithMissingSlice()

        for patient,pval in tqdm(self.image_loader.items(),desc = 'Extract to .nii.gz ', colour='CYAN'):
            
            if patient not in nii_dict:
                
                nii_dict[patient] = {}

            for study,stval in pval.items():

                T2dict = {}
                segment_dict = {}
                if 'T2' in stval:
                    nii_dict[patient][study] = {}
    
                    T2dict = stval['T2']['N/A']['dcm_path']
                    T2series = stval['T2']['N/A']['meta']['series_uid']
    
                    T2_list_path = [T2dict[pos]['path'] for pos in T2dict]
                    T2 = SitkUtils.LoadImageByFolder(T2_list_path, 'LPS')
    
                    if 'SEG' in stval:
                        segment_dict = stval['SEG']
                    else:
                        segment_dict = {}
                    
                    if  not segment_dict:
                        self.missing_seg_list.append([patient, study])
    
                    label_list = [seg for seg in segment_dict ]
    
                    for seg in label_list:
                            seg_path = segment_dict[seg]['nii_path']
                            segment_dict[seg]['image'] = SitkUtils.LoadSingleFile(seg_path, 'LPS')


                ADCdict = {}
                if 'ADC' in stval:

                    ADCdict = stval['ADC']['N/A']['dcm_path']
                    ADCseries = stval['ADC']['N/A']['meta']['series_uid']

                    rescale_type = None
                    if 'rescale_type' in stval['ADC']['N/A']['meta']:
                        rescale_type = stval['ADC']['N/A']['meta']['rescale_type']
                        

                    
                    ADC_list_path = [ADCdict[pos]['path'] for pos in ADCdict]

                    ADC = SitkUtils.LoadImageByFolder(ADC_list_path, 'LPS')
                    
                    max_value = sitk.GetArrayFromImage(ADC).max()
                    
                    if (rescale_type == "10^-3 mm^2/s") or (max_value < 10):
                        
                        self.logger.LogIssue("ADCRescaleTypeMicro",{f'{patient}_{study}':f'Max Value is {max_value}, dicom tag rescale type is {rescale_type}'})
                        ADC = self.ADCMicro2Nano(ADC)

                DWIdict = {}
                if 'DWI' in stval:

                    if self.keep_max_bvalue:
                        
                        DWIdict = stval['DWI']
                        Bvalues = list(DWIdict.keys())
                        DWIseries = stval['DWI'][Bvalues[0]]['meta']['series_uid']

                        count_Unknown = 0
                        for b in Bvalues:

                            if 'Unknown' in b:
                                count_Unknown += 1
                        
                        if len(Bvalues) == 1:

                            bval = Bvalues[0]

                        elif count_Unknown == len(Bvalues):

                            bval = None

                            if patient in self.exclude_dict:

                                if study in self.exclude_dict[patient]:

                                    bval = self.exclude_dict[patient][study]

                            if not bval:

                                bval = Bvalues[-1]

                        else:

                            bval = '0'

                            for b in Bvalues:

                                if 'Unknown' not in b:

                                    if '-' in b:
                                        self.logger.LogIssue("SameBValueFound",{f"{patient}_{study}": f"Has {b} and {b.split('-')[0]} inside, check image_loader.json"})

                                    elif int(b) > int(bval):

                                        bval = b

                        self.D = copy.deepcopy(DWIdict)
                        self.bval = bval
                        DWIdict = { bval:
                                        {'path':    [
                                                        path['path']  
                                                        for path in DWIdict[bval]["dcm_path"].values()
                                                    ]
                                        }
                        }
                            
                        DWI_list_path = DWIdict[bval]['path']
                        DWIdict[bval]['image'] = SitkUtils.LoadImageByFolder(DWI_list_path, 'LPS')
            
                    else: #keep all available DWIs

                        DWIdict = stval['DWI']
                        Bvalues = list(DWIdict.keys())
                        DWIseries = stval['DWI'][Bvalues[0]]['meta']['series_uid']

                        DWIdict = { bvalue: 
                                            {'path':
                                                        [
                                                            path['path']  
                                                            for path in DWIdict[bvalue]["dcm_path"].values()
                                                        ]
                                            }
                                    for bvalue in DWIdict
                        }
                        
                        for bval in DWIdict:
                            
                            DWI_list_path = DWIdict[bval]['path']
                            DWIdict[bval]['image'] = SitkUtils.LoadImageByFolder(DWI_list_path, 'LPS')

                DCEdict = {}
                if 'DCE' in stval:

                    DCEdict = stval['DCE']['N/A']['dcm_path']
                    ADCseries = stval['DCE']['N/A']['meta']['series_uid']

                    rescale_type = None
                    if 'rescale_type' in stval['DCE']['N/A']['meta']:
                        rescale_type = stval['DCE']['N/A']['meta']['rescale_type']
                        

                    
                    DCE_list_path = [DCEdict[pos]['path'] for pos in DCEdict]

                    DCE = SitkUtils.LoadImageByFolder(DCE_list_path, 'LPS')
                
 
                export_path = os.path.join(extract_folder, patient, study)
                os.makedirs(export_path, exist_ok=True)

                if T2dict:
                    SitkUtils.WriteDICOM2Nifti(T2, export_path, 'T2')
                    nii_dict[patient][study]['T2'] = os.path.join(export_path,'T2.nii.gz').replace('\\','/')

                if ADCdict:

                    SitkUtils.WriteDICOM2Nifti(ADC, export_path, 'ADC')
                    nii_dict[patient][study]['ADC'] = os.path.join(export_path,'ADC.nii.gz').replace('\\','/')

                if DWIdict:
                    
                    for bval,DWIval in DWIdict.items():
                        SitkUtils.WriteDICOM2Nifti(DWIval['image'], export_path, f'DWI_{bval}')
                        nii_dict[patient][study][f'DWI_{bval}'] = os.path.join(export_path,f'DWI_{bval}.nii.gz').replace('\\','/')

                if DCEdict:

                    for bval,DWIval in DWIdict.items():
                        SitkUtils.WriteDICOM2Niifty(DCEdict['image'], export_path, f'DCE')
                        nii_dict[patient][study][f'DCE'] = os.path.join(export_path,f'DCE.nii.gz').replace('\\','/')

                if segment_dict:

                    for seg,SEGval in segment_dict.items():
                        SitkUtils.WriteDICOM2Nifti(SEGval['image'], export_path, f'{seg}')
                        nii_dict[patient][study][f'{seg}'] = os.path.join(export_path,f'{seg}.nii.gz').replace('\\','/')

                JsonUtils.Write(nii_dict, 'nifti_files.json')
