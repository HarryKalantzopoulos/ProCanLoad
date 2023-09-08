from setuptools import setup

setup(
    name='ProCanLoad',
    
    version='1.0-beta',
    
    description='ProCAncer-I image loading tool',
    
    authors= "Kalantzopoulos Charalampos",

    author_email='xkalantzopoulos@gmail.com',

    packages=['ProCanLoad'],

    url='https://github.com/HarryKalantzopoulos/ProCanLoad',

    install_requires=[
        'SimpleITK==2.2.1',
        'pydicom',
        'tqdm'
    ]
)
