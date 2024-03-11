from setuptools import setup

setup(
    name='ProCanLoad',
    
    version='0.0.1-dev',
    
    description='ProCAncer-I image loading tool - no parquet',
    
    authors= "Kalantzopoulos Charalampos",

    author_email='xkalantzopoulos@gmail.com',

    packages=['ProCanLoad'],

    url='https://github.com/HarryKalantzopoulos/ProCanLoad',

    install_requires=[
        'simpleitk>=2.1',
        'pydicom',
        'tqdm'
    ]
)
