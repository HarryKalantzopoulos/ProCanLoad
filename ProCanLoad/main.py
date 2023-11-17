import os
from pathlib import Path
import yaml
import importlib.util
import argparse
import warnings

 
package_name = 'ProCanLoad'
 
if importlib.util.find_spec(package_name) is None:
    os.system('pip install git+https://github.com/HarryKalantzopoulos/ProCanLoad.git')

from ProCanLoad.ImageLoader import ImageLoader, DICOM2NII


def dicom2nii(series: Path = '', 
              segmentations:Path = '', 
              images_directory_path:Path = '' 
            ):
    
    inputs = 'params.yaml'
    
    if os.path.isfile(inputs):

        inputs = yaml.safe_load( open(inputs) )
    
    if not ('series_df'  in inputs or 
            'images_dir' in inputs):
        inputs = ''




    if not os.path.isdir(images_directory_path):
        
        if not inputs:
            raise FileNotFoundError(images_directory_path)
        
        images_directory_path = inputs['images_dir']

    if not os.path.isfile(series):
        
        if not inputs:
            raise FileNotFoundError(series)
        
        series = inputs['series_df']

    if not os.path.isfile(segmentations):

        if 'segments_df' in inputs:
            segmentations = inputs["segments_df"]
        
        else:
            segmentations = ''
            warnings.warn("Segmentation FileNotFound, proceed without extracting seg images!")

    if segmentations:
        loader = ImageLoader(
                            images_directory_path = images_directory_path,
                            parquet_series = series,
                            parquet_segmentations = segmentations
                            )
    else:
        loader = ImageLoader(
                            images_directory_path= images_directory_path,
                            parquet_series=series
                            )

    loader.GetImageLoader()

    extractor = DICOM2NII(image_loader='image_loader.json')
    
    extractor.Excecute()


if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument("--series", type=str, help="path/to/ecrfs-series-{version}.parquet", default='')
    parser.add_argument("--segments", type=str, help="path/to/segments-{version}.parquet", default='')
    parser.add_argument("--image-dir", type=str, help="path/to/{image directory}", default='')
    args = parser.parse_args()

    series_arg = args.series
    segments_arg = args.segments
    images_arg = args.image_dir

    dicom2nii(series_arg, segments_arg, images_arg)