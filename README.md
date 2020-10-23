# irccam-pmodwrc
Cloud detection using the IRCCAM at PMOD/WRC

## Install dependencies
Make sure you have pipenv and pyenv installed, then you can run:
```
pipenv install 
```

## Running notebooks
To run jupyter notebook with the project virtual env:
```
pipenv shell
jupyter notebook
```
OR
```
pipenv run jupyter notebook
```

You may need to create a kernel for jupyter notebook with 
```
python -m ipykernel install --user --name=irccam
```
Then, in jupyter notebook select Kernel -> Change kernel -> irccam.

## Data
The `data` folder is ignored by git, but we should use a consistent structure
locally to make it easy to work with data in the code. The structure is 
currently:
```
.
└── data/
    ├── raw/
    │   ├── davos/
    │   │   ├── irccam
    │   │   └── rgb
    │   └── geneva/
    │       ├── irccam
    │       └── rgb
    └── datasets/
        ├── dataset_1/
        │   ├── train/
        │   │   ├── irccam
        │   │   └── labels
        │   ├── val/
        │   │   └── ...
        │   └── test/
        │       └── ...
        └── ...
```
