# ProCAnLoad

![ProCAncer-I](https://www.procancer-i.eu/wp-content/uploads/2020/07/logo.png)

[![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04-dd4814?logo=ubuntu&logoColor=white&style=flat-square)](https://ubuntu.com/)
[![Windows](https://img.shields.io/badge/Windows-11-0078d4?logo=windows&logoColor=white&style=flat-square)](https://www.microsoft.com/en-us/windows/)

ProCAnLoad is an image loader for ProCAncer-I dataset and segmentation files. After you filtered the .parquet file on which series to keep, and drop out the unnecessary ones. You can input the modified parquet to:

i) Create a dictionary with all the patients, stored as image_loader.json.

ii) Extract the available segmentations from the segmentation .dcm file.

iii) Extract DICOM images to Niifty (.nii.gz) which their path will be stored in nifty_files.nii

iv) Provides a logger to catch any warning, for the user to check, stored in issues/issues_image_loader.json

The package makes use of SimpleITK and pydicom.

# Requirements
simpleitk>=2.1

pydicom

tqdm

pyyaml

pandas

numpy

pyarrow

# Install repository:
run 
```bash
pip install git+https://github.com/HarryKalantzopoulos/ProCAnLoad.git@dev_nometa
```
# Demonstration
```python
# Let's say files in dir "image_repository"
# ProCAncer-I data only uses the name of the parent folder of the dcm files for description. If not then the ones from the parquet files and then the series description.
from ProCanLoad.ExtractMeta import ReadMeta
from ProCanLoad import ImageLoader

path2images = "image_repository"
ReadMeta(path2images) # Now, will work for dcm files !
# creates 'ecrfs.parquet', 'segments.parquet'
Loader = ImageLoader(path2images,'ecrfs.parquet','segments.parquet',extract_nii=True)
Loader.GetImageLoader()

# Read the nifti_files.json for the paths to each nii.gz file for each patient and study.
```

# Authors

Kalantzopoulos Charalampos, xkalantzopoulos@gmail.com

Zaridis Dimitrios dimzaridis@gmail.com

Mylona Eugenia mylona.eugenia@gmail.com

Nikolaos Tachos ntachos@gmail.com

```
@misc{Kalantzopoulos2023,
  author = {Kalantzopoulos, Charalampos},
  title = {ProCAncer-I, DICOM to NIfTI conversion},
  year = {2023},
  version = {1.1},
  publisher = {github},
  howpublished = {\url{https://github.com/HarryKalantzopoulos/ProCanLoad}},
}
```
