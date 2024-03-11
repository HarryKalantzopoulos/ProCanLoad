# Requires ecrfs parquet

# A = pd.read_parquet('ecrfs-series-20240226.parquet')
# # just stats
# A.user_series_type.value_counts()
# A.catboost_series_type_heuristics.value_counts()

# my_dict = {'T2':[],
#           'ADC':[],
#           'DWI':[],
#           'DCE':[],
#           'OTHER':[]
# }

# for row in range(len(A)):

#     temp = A.iloc[row]

#     if temp.user_series_type:

#         if temp.user_series_type == 'T2AX':
#             if temp.series_description not in my_dict[ 'T2' ]:
#                 my_dict['T2'].append(temp.series_description)

#         else:

#             if temp.user_series_type in my_dict.keys():
#                 if temp.series_description not in my_dict[ temp.user_series_type ]:
#                     my_dict[ temp.user_series_type ].append(temp.series_description)

    
#     elif temp.catboost_series_type_heuristics:

#         if temp.catboost_series_type_heuristics in my_dict.keys():
            
#             if temp.series_description not in my_dict[ temp.catboost_series_type_heuristics ]:
                
#                 my_dict[ temp.catboost_series_type_heuristics ].append(temp.series_description)


# with open('series_description.yaml','w') as f:

#     yaml.dump(my_dict,f,indent=4,sort_keys=False)

import SimpleITK as sitk
import pydicom
import pandas as pd
import yaml
from pathlib import Path
import os

def get_directories (path:Path, filetype:str = '.dcm') -> list:

    path_list = []
    for dirpath,_,files in os.walk(path):

        for file in files:

            if file.endswith(filetype):

                path_list.append(dirpath)


    return list(set(path_list))

def get_dcm_file(dir_list:list) -> list:

    sample_list = []
    for dirpath in dir_list:

        for file in os.listdir(dirpath):

            if file.endswith('.dcm'):
                temp = os.path.join(dirpath, file)
                sample_list.append(temp)
                break
    
    return sample_list

def read_file_image(dcm_path: Path) -> tuple[sitk.Image, pydicom.Dataset]:

    try:
        sitk_image = sitk.ReadImage(dcm_path)
    except: #fails in some segmentation files
         sitk_image = None
         
    dcm_image = pydicom.dcmread(dcm_path)

    return sitk_image, dcm_image


# First 2D Image
def ReadMeta(image_repository:Path,filetype:str = '.dcm') -> pd.DataFrame:

    dir_list = get_directories(image_repository, filetype)
    file_list = get_dcm_file(dir_list = dir_list)

    series_yaml = yaml.safe_load(open('series_description.yaml','r'))

    default_ecrfs = {
                                'provided_by':'0008|0080',
                                'patient_id':'0010|0020', 
                                'study_uid':'0020|000d', 
                                'series_uid':'0020|000e',
                                'series_description':'0008|103e',  
                                'user_series_type':None,
                                'catboost_series_type_heuristics':None,
                                'diffusion_bvalue': 0, # Not searching, done after
                                'manufacturer':'0008|0070',
                                'manufacturer_model_name':'0008|1090',
                                'use_case_form':'0008|1030'
    }

    ecrfs = { key: [] for key in default_ecrfs }

    segments = {    'source_series_uid':[],
                    'study_uid':[],
                    'derived_series_uid':[],
    }

    for file in file_list:
        
        sitk_image, dcm_image = read_file_image(file)
        #seg
        if isinstance(sitk_image, sitk.Image):
            statement = sitk_image.GetMetaData("0008|0060").upper().strip()
            # print(sitk_image.GetMetaData('0008|103e'), sitk_image.GetMetaData("0008|0060"))
        else:
            statement = 'SEG'

        if statement == 'SEG':

            source_series = dcm_image[0x0008,0x1115][0][0x0020, 0x000e].value
            
            segments['study_uid'].append(dcm_image.StudyInstanceUID.strip())
            segments['source_series_uid'].append(source_series.strip())
            segments['derived_series_uid'].append(dcm_image.SeriesInstanceUID.strip())

        #ecrfs 
        else:
            # available_keys = img.GetMetaDataKeys()

            for key,value in default_ecrfs.items():
                if value:
                    ecrfs[key].append(sitk_image.GetMetaData(value).strip())
                elif value == 0:
                    ecrfs[key].append('0')
                elif value is None:
                    series_description = sitk_image.GetMetaData('0008|103e')
                    find_value = False
                    
                    for k,v in series_yaml.items():
                        
                        if series_description in v:
                            ecrfs[key].append(k)
                            find_value = True
                            break
                        
                    if not find_value:
                        series_description = series_description.upper().strip()
                        if 'T2' in series_description:
                            ecrfs[key].append('T2')
                        elif ('ADC' in series_description) or ('APPAR' in series_description):
                            ecrfs[key].append('ADC')
                        elif ('DWI' in series_description) or ('DIFF' in series_description):
                            ecrfs[key].append('DWI')
                        else:
                            ecrfs[key].append(series_description)

    # return ecrfs, segments

    ecrfs_df = pd.DataFrame.from_dict(ecrfs)
    segments_df = pd.DataFrame.from_dict(segments)

    ecrfs_df.to_parquet('ecrfs.parquet', index= False)
    segments_df.to_parquet('segments.parquet', index= False)

'''
How to use:

Let's say files in dir "image_repository"
Still needs to be in ProCAncer-I format (PATIENT_ID/STUDY_UID/SERIES_UID), modifications must be done in ImageLoader

from ProCanLoad.ExtractMete import ReadMeta
from ProCanLoad import ReadMeta, ImageLoader

path2images = "image_repository"
ReadMeta(path2images) # Now, will work for dcm files !
# creates 'ecrfs.parquet', 'segments.parquet'
Loader = ImageLoader(path2images,'ecrfs.parquet','segments.parquet',extract_nii=True)
Loader.GetImageLoader()
'''
