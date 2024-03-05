from setuptools import setup

setup(
    name='ProCanLoad',
    
    version='1.1-beta',
    
    description='ProCAncer-I image loading tool',
    
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
