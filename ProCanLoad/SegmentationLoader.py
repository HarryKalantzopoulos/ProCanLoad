import os
from pathlib import Path
import SimpleITK as sitk
import pydicom
import pandas as pd
import numpy as np

from .utils import DataFrameUtils
from .sitk_utils import SitkUtils
from .IssueLogger import IssueLogger

class SegmentationLoader():

    def __init__(self,  images_directory_path: Path,
                        parquet_series: Path or pd.DataFrame,
                        parquet_segmentations: Path or pd.DataFrame,
                        reset_logger:bool = False

    ) -> None:
        
        self.images_directory_path = images_directory_path
        self.parquet_series = parquet_series
        self.parquet_segmentations = parquet_segmentations

        self.logger = IssueLogger(reset = reset_logger)


    @staticmethod
    def CreateLabelDict(seg: pydicom.Dataset):
        '''
        Create a dictionary with the labels inside the seg file. 
        '''
        label_dictionary = {}
        
        for sed_id in seg[0x0062,0x0002]:
            id = sed_id[0x0062,0x0004].value
            name = sed_id[0x0062,0x0005].value
            label_dictionary[id] = name

        return dict( sorted ( label_dictionary.items() ) )
    
    def CorrectLabelDict2Ref(self, seg: pydicom.Dataset, label_dict: dict):
        '''
        Segmentation dcm files give a one-hot-encoded value (DICOM tag [0062,0004]) for each label, however from 1 Aug version for some segmentation files,
        there are some bad encodement in Referenced Segment Number of each slice (DICOM tag [ 0x0062, 0x000b] ). Thus the new addition in this case. 
        '''

        available_reference_codes = list ( set( [ ref[0x0062, 0x000a][0][ 0x0062, 0x000b].value for ref in seg[0x5200, 0x9230] ] ) )
        label_names = [ name for name in label_dict.values() ]
        encoded_labels = list(label_dict.keys())

        if available_reference_codes == encoded_labels:
            pass
        
        elif  len(available_reference_codes)  == len(encoded_labels):
            
            label_dict = { code : name for code, name in zip(available_reference_codes, label_names) }
            self.logger.LogIssue( 'EncodingMismatch', {f'{self.seg_series}':f'Warning: Encoded labels in [0062,0004] does not much the one or more reference(s) [ 0x0062, 0x000b]'} )

        else:
            label_dict = {available_reference_codes[i]:label_names[i]
                for i in range( len(available_reference_codes) ) }
            self.logger.LogIssue( 'LabelMismatch', {f'{self.seg_series}':f'Warning: The number of Encoded labels in [0062,0004] does not much the reference [ 0x0062, 0x000b]. This means that something might be missing or the extracted files might not be named with the correct label'} )
        
        return label_dict

    def MatchSliceIDSeg2Img(self, series_dict):


        self.study = series_dict['meta']['study_uid']
        self.series = series_dict['meta']['series_uid']

        self.df = DataFrameUtils.Read(self.parquet_series)
        self.df_seg = DataFrameUtils.Read(self.parquet_segmentations)
        
        self.seg_series = self.df_seg[ self.df_seg.source_series_uid == self.series].derived_series_uid.iloc[0]

        self.patient = self.df [self.df.series_uid == self.series].patient_id.values[0]
        
        #Get path to image_slices
        image_dict_path = series_dict['dcm_path'].copy()
        self.test_origin = float( list(image_dict_path.keys())[0] )
        self.image_list_path = [path['path'] for  path in image_dict_path.values()]
        
        #Load image slice 1 by 1 and get slice unique id
        sop_uid_list = []

        for image_path in self.image_list_path:    
   
            image = sitk.ReadImage(image_path)
            sop_uid = image.GetMetaData("0008|0018")
            sop_uid_list.append(sop_uid)

        xyzsize = [len(self.image_list_path)]  # Slices from source image
        xysize = list(image.GetSize()[::-1][1:3]) # Only x,y needed
        xyzsize.extend(xysize) 

        #Load segmentation
        segmentation_path = os.path.join(self.images_directory_path, self.patient, self.study, self.seg_series, 'image-001.dcm')
        seg = pydicom.dcmread(segmentation_path)
        seg_im = seg.pixel_array

        labels = self.CreateLabelDict(seg)
        labels = self.CorrectLabelDict2Ref(seg, labels)

        #Find the segmentation from reference and type of segmentation
        self.segment_dict = {}

        for slice_seg, ref_per_frame in enumerate(seg[0x5200, 0x9230]):
                
            ref_sop_uid = ref_per_frame[0x0008, 0x9124][0][0x0008, 0x2112][0][0x008,0x1155].value

            ref_seg_encoded = ref_per_frame[0x0062, 0x000a][0][ 0x0062, 0x000b].value #Hot-encoded of label

            label_name = labels[ref_seg_encoded]

            if ref_sop_uid in sop_uid_list:

                loc_in_image = sop_uid_list.index(ref_sop_uid) #Find location of reference seg's slice inside source image's slices

                if label_name not in self.segment_dict:
                    
                    self.segment_dict[label_name] = np.zeros(xyzsize,dtype=np.uint8) #Initialize mask for the corresponding label

                if seg_im.ndim == 2:

                    self.segment_dict[label_name][loc_in_image] = seg_im.copy()
                    self.logger.LogIssue( 'OneSliceSegmentation', {f'{self.seg_series}_{label_name}':f'Has only 1 2D slice'} )

                elif seg_im.ndim == 3:

                    self.segment_dict[label_name][loc_in_image] = seg_im[slice_seg].copy()

            else:

                self.logger.LogIssue( 'SegmentationSliceReferenceNotFound', {f'{self.seg_series}':f'The reference slice id (SOP UID) did not match the T2 ones. Unable to extract segmentations for {self.patient}'} )

    def WriteSegmentation(self):

        imageITK = SitkUtils.LoadImageByFolder(self.image_list_path)
        assert self.test_origin in imageITK.GetOrigin(), f"Origin mismatch when loading images \n first slice location: {self.test_origin}\n loaded_image: {imageITK.GetOrigin()}"

        segment_labels = { }
        zero_mask = { }

        for label in self.segment_dict:

            output = os.path.join('seg_files',self.patient,self.study,self.seg_series)
            os.makedirs(output,exist_ok=True)
            output = os.path.join(output,f'{label}.nii.gz')

            mask = self.segment_dict[label]

            if len(np.unique(mask)) == 2:
            
                segment_labels[label] = {  'meta':{
                                                    'patient_id': self.patient,
                                                    'study_uid': self.study,
                                                    'T2_series_uid': self.series,
                                                    'seg_series_uid': self.seg_series,
                                                    'type':'binary'
                                            },
                                            'nii_path': output
                }

                if mask.max() != 1:
                    mask[mask>0] = 1
        
            elif len(np.unique(mask)) > 2:

                segment_labels[label] = {  'meta':{
                                                    'patient_id': self.patient,
                                                    'study_uid': self.study,
                                                    'T2_series_uid': self.series,
                                                    'seg_series_uid': self.seg_series,
                                                    'type':'semantic'
                                            },
                                            'nii_path': output
                }

                                                
            elif mask.max() == 0:
                #Report but do not write zero-mask
                zero_mask[label] = {    'meta':{
                                                    'patient_id': self.patient,
                                                    'study_uid': self.study,
                                                    'T2_series_uid': self.series,
                                                    'seg_series_uid': self.seg_series,
                                                    'type':'semantic'
                                        },
                                        'nii_path': None
                }

                continue
            

            mask_itk = sitk.GetImageFromArray(mask)

            assert imageITK.GetSize() == mask_itk.GetSize()

            mask_itk.CopyInformation(imageITK)
            mask_itk = sitk.Cast(mask_itk, sitk.sitkUInt8)

            sitk.WriteImage(mask_itk, output)

        return segment_labels, zero_mask
        
    def GetSeriesSegmentations(self, T2series_dict):

        self.MatchSliceIDSeg2Img(T2series_dict)
        
        return self.WriteSegmentation()