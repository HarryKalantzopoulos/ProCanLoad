import os
from pathlib import Path
import numpy as np
import SimpleITK as sitk

class SitkUtils():

    @staticmethod
    def GetFiles(series_path: Path) -> tuple:
         
        reader=sitk.ImageSeriesReader()
        return reader.GetGDCMSeriesFileNames(series_path)

    #%% dcm image related process
    @staticmethod
    def LoadImageByFolder(image_list: list or tuple, orientation:str = None) -> sitk.Image:
        '''
        Load ITK image from the directory and filter itk paths not in  list of paths
        '''


        reader=sitk.ImageSeriesReader()

        reader.SetFileNames(image_list)
        reader.MetaDataDictionaryArrayUpdateOn()
        reader.LoadPrivateTagsOn()
        ITK = reader.Execute()

        if orientation:
             ITK = sitk.DICOMOrient(ITK,orientation)

        return ITK
    
    @staticmethod
    def ReadImageInfo(filepath: Path) -> sitk.Image:
        '''
        Load metadata
        '''
        inforeader = sitk.ImageFileReader()
        inforeader.SetFileName(filepath)
        inforeader.LoadPrivateTagsOn()
        inforeader.ReadImageInformation()

        return inforeader
    
    @staticmethod
    def LoadSingleFile( filepath: Path, orientation:str = None )-> sitk.Image:
        '''
        Load one file, !does not load private tags!
        '''

        image = sitk.ReadImage(filepath)
        
        if orientation:
             image = sitk.DICOMOrient(image,orientation)
             
        return image
    
    @staticmethod
    def GetImagePlane(image: sitk.Image) -> str:
            '''
            Get Image Plane orientation
            '''

            directions = image.GetDirection()

            directions = (directions[0], directions[3], directions[6], directions[1], directions[4], directions[7])

            idx = abs(np.cross(directions[0:3],directions[3:6])).argmax()

            return str(idx)
    
    @staticmethod
    def GetBvalue(image:sitk.Image) -> str:
        '''
        Retrieve B-values if exist, and if the sequence is DWI.
        DICOM tags universal,non-private (0018,9087)
                    SIEMENS private tag   (0019,100C)
                    GE private tag        (0043,1039)

        '''

        to_check = image.GetMetaDataKeys()

        #Public dicom tag for bvalues
        if "0018|9087" in to_check:
            tag = "0018|9087"

        #Siemens private tag for bvalues
        elif "0019|100c" in to_check:
            tag = "0019|100c"

        #GE private tag for bvalues
        elif "0043|1039" in to_check:
            tag = "0043|1039"
        
        #No values    
        else:
            return "N/A"

        return image.GetMetaData(tag)
    
    @staticmethod
    def WriteDICOM2Niifty(image: sitk.Image or list,path2save: Path, sequence: str) -> None:

        os.makedirs(path2save, exist_ok=True)

        if isinstance(image,list) or isinstance(image,tuple):

            ITKim = SitkUtils.LoadImageByFolder(image, orientation= 'LPS')

        else:

            ITKim = image

        path = os.path.join(path2save, sequence+'.nii.gz' )
        sitk.WriteImage(ITKim, path)

    #### Not used. Decoding is performed by pydicom. SimpleITK may fail to read some bvalues.
    # import base64 #Package needed for decoding 
    # def DecodeBvalue(self,value):
    #     '''
    #     Bvalues are strings that may contain int, encoded base64 int or decoded as 100000(bvalue)//8//0//0 or bvalue//8//0//0
    #     '''
    #     if isinstance(value,str):
    #         if not value:
    #             return 'N/A'

    #     if isinstance(value,int):
    #         return value
        
    #     value_a = value.strip()
    #     if value_a.isnumeric():
    #             return int(value_a)

    #             #String returned these values like
    #             #"1000000050\\8\\0\\0", "1000000800\\8\\0\\0", "1000001400\\8\\0\\0", "1400\\8\\0\\0", "1000\\8\\0\\0"
    #     if '\\' in value_a:
    #         value_b = value_a.split('\\')[0]
    #         return int(value_b[-4:])
    #     else:
    #         temp = base64.b64decode(value_a).decode("utf-8")
    #         temp = temp.strip()
    #         if temp.isnumeric():
    #                 return int(temp)
    #         else:
                  # Again string with slashes in it.
    #             temp = temp.split('\\')[0]
    #             return int(temp[-4:])

    # def GetBvalues(self,image):
    #     '''
    #     Retrieve B-values if exist, and if the sequence is DWI.
    #     DICOM tags universal,non-private (0018,9087)
    #                SIEMENS private tag   (0019,100C)
    #                GE private tag        (0043,1039)

    #     '''

    #     to_check = image.GetMetaDataKeys()

    #     #Public dicom tag for bvalues
    #     if "0018|9087" in to_check:
    #         tag = "0018|9087"

    #     #Siemens private tag for bvalues
    #     elif "0019|100c" in to_check:
    #         tag = "0019|100c"

    #     #GE private tag for bvalues
    #     elif "0043|1039" in to_check:
    #         tag = "0043|1039"
        
    #     #No values    
    #     else:
    #         tag = "N/A"  

    #     if tag == "N/A":
    #          return tag
            
    #     bvalue = image.GetMetaData(tag)

    #     return self.DecodeBvalue(bvalue)