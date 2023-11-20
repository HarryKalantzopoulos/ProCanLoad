import pydicom
import numpy as np
import struct
from pathlib import Path
from .utils import GetDirectionDict

class DCMUtils():

    @staticmethod
    def ReadSlice(path: Path) -> pydicom.FileDataset:

        return pydicom.dcmread(path)
    
    @staticmethod
    def GetBvaluesTags():
        # All the current knows tags for b-values
        bvalues_tags = [    (0x0018,0x9087), #Public dicom tag for bvalues
                            (0x0019,0x100c), #Siemens private tag for bvalues
                            (0x0043,0x1039), #GE/Philips private tag for bvalues. Pydicom has a problem in decoding some bvalues for Philips, will remain bytes, simpleITK returns None
                            None             #Value is missing, currently no other tag was found to represent b-value
                        ]
        
        return bvalues_tags
    
    def DecodeBValue(bval: bytes):

        if '\\x' in str(bval):

            # Undecoded values, little endian
            val = struct.unpack('<d',b_val)[0]
            return str(int(val)),'DecodedInt'
        
        elif '\\' in str(bval):
            #format masked: (10^9+)bvalue//8//...
            b_str = bval.decode().split('\\')[0]
            val = b_str[-4:]
            return int(val),'Bytes2String2Int'

        else:
            return str(int(bval)),'Bytes2Int'

    def GetBValue(dcm_image: pydicom.FileDataset):

        bvalues_tags = DCMUtils.GetBvaluesTags()
        b_iter = iter(bvalues_tags)
        b_tag = next(b_iter)
        
        while (b_tag not in dcm_image):
            b_tag = next(b_iter)
            if b_tag is None:
                break

        if b_tag == None:
            return b_tag,'Unknown'
        
        bvalue = dcm_image[b_tag].value

        if isinstance(bvalue,bytes):
            
            value, message = DCMUtils.DecodeBValue(bvalue)
            return value, message
        
        elif isinstance(eval(str(bvalue)),list):
            #[(10^9+)bvalue,8,...] but MultiValue object!!!
            b_list = eval(str(bvalue))
            return str(b_list[0])[-4:],'MultiValue2String'

        return str(int(bvalue)),'normal'
