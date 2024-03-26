import json
import pandas as pd
from pathlib import Path

class DataFrameUtils:

    @staticmethod
    def Read(file: str | pd.DataFrame) -> pd.DataFrame:

        PandasLoaderDict = {    '.csv':     pd.read_csv,
                                '.xlsx':    pd.read_excel,
                                '.parquet': pd.read_parquet
        }

        if isinstance(file, str):
            
            if not Path(file).exists():
                raise FileNotFoundError(f'Path to parquet:{file}')
            
            suffix = Path(file).suffix
            
            if suffix not in PandasLoaderDict:
                raise ValueError(f"I haven't build this path yet. Unknown {suffix}")

            return PandasLoaderDict[suffix](file)

        if isinstance(file,pd.DataFrame):
            
            return file

class JsonUtils:
    
    @staticmethod
    def Write(adict:dict, path:Path):
            '''
            Write dictionary to json file at the selected path
            '''
            with open(path,'w') as f:
                
                json.dump(adict,f,indent=4)
    @staticmethod
    def Load(path:Path):
        '''
        Load json file at the selected path
        '''
        with open(path,'r') as f:

            return json.load(f)
        

def GetDirectionDict() -> dict:
     
    direction_dict =    {   '0': {'plane':'SAG','origin':0}, # Sagittal
                            '1': {'plane':'COR','origin':1}, # Coronal
                            '2': {'plane':'AX', 'origin':2}  # Axial
        }
 
    return direction_dict
