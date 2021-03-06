# -*- coding: utf-8 -*-
"""AnotherNotebookTrainingDCIS:"

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1p8NT58_9brUjpWMML4_hamKBGQMFYjMk
"""

!python -m pip install histomicstk --find-links https://girder.github.io/large_image_wheels

import histomicstk as htk

import numpy as np
import scipy as sp

import skimage.io
import skimage.measure
import skimage.color

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
import torchvision
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import *
import os
import zipfile
import shutil
from tqdm.auto import tqdm
import tqdm
from imageio import *
from torchvision import *
import torchvision.transforms as transforms
dev='cpu'
if torch.cuda.is_available():
  dev='cuda'
dev=torch.device(dev)
plt.style.use('fivethirtyeight')

from google.colab import drive
drive.mount('/content/drive')

!unzip /content/drive/MyDrive/5_DCIS_train.zip

for i in os.listdir('/content/5_DCIS'):
  ok=i.split('.');
  if ok[1]!='png' or len(ok)>2:
    print(i)
    shutil.rmtree(os.path.join('/content/5_DCIS',i))

List_paths=[]
D=[]
N=[]
for i in os.listdir('/content/5_DCIS')[:357]:
  D.append([os.path.join('/content/5_DCIS',i),1]);
  # N.append([os.path.join('/content/drive/MyDrive/0_N',j),0])
for i in os.listdir('/content/drive/MyDrive/0_N'):
  N.append([os.path.join('/content/drive/MyDrive/0_N',i),0])
indx1=0;
indx2=0;
for i in range(357*2):
  if i%2==0:
    List_paths.append(D[indx1]);
    indx1+=1;
  else:
    List_paths.append(N[indx2])
    indx2+=1;

ref_image_file = ('/content/drive/MyDrive/L1.png') 
im_reference = skimage.io.imread(ref_image_file)[:, :, :3]
def get_nuclei_den(image,im_reference=im_reference):
  im_input = image
  '''plt.imshow(im_input)
  _ = plt.title('Input Image', fontsize=16)'''

   # L1.png


  # get mean and stddev of reference image in lab space
  mean_ref, std_ref = htk.preprocessing.color_conversion.lab_mean_std(im_reference)

  # perform reinhard color normalization
  im_nmzd = htk.preprocessing.color_normalization.reinhard(im_input, mean_ref, std_ref)

  # Display results
  '''plt.figure(figsize=(20, 10))

  plt.subplot(1, 2, 1)
  plt.imshow(im_reference)
  _ = plt.title('Reference Image', fontsize=titlesize)

  plt.subplot(1, 2, 2)
  plt.imshow(im_nmzd)
  _ = plt.title('Normalized Input Image', fontsize=titlesize)'''

  stainColorMap = {
      'hematoxylin': [0.65, 0.70, 0.29],
      'eosin':       [0.07, 0.99, 0.11],
      'dab':         [0.27, 0.57, 0.78],
      'null':        [0.0, 0.0, 0.0]
  }

  # specify stains of input image
  stain_1 = 'hematoxylin'   # nuclei stain
  stain_2 = 'eosin'         # cytoplasm stain
  stain_3 = 'null'          # set to null of input contains only two stains

  # create stain matrix
  W = np.array([stainColorMap[stain_1],
                stainColorMap[stain_2],
                stainColorMap[stain_3]]).T

  # perform standard color deconvolution
  im_stains = htk.preprocessing.color_deconvolution.color_deconvolution(im_nmzd, W).Stains

  # Display results
  '''plt.figure(figsize=(20, 10))

  plt.subplot(1, 2, 1)
  plt.imshow(im_stains[:, :, 0])
  plt.title(stain_1, fontsize=titlesize)

  plt.subplot(1, 2, 2)
  plt.imshow(im_stains[:, :, 1])
  _ = plt.title(stain_2, fontsize=titlesize)'''
  im_nuclei_stain = im_stains[:, :, 0]

  # segment foreground
  foreground_threshold = 60

  im_fgnd_mask = sp.ndimage.morphology.binary_fill_holes(
      im_nuclei_stain < foreground_threshold)

  # run adaptive multi-scale LoG filter
  min_radius = 10
  max_radius = 15

  im_log_max, im_sigma_max = htk.filters.shape.cdog(
      im_nuclei_stain, im_fgnd_mask,
      sigma_min=min_radius * np.sqrt(2),
      sigma_max=max_radius * np.sqrt(2)
  )

  # detect and segment nuclei using local maximum clustering
  local_max_search_radius = 10

  im_nuclei_seg_mask, seeds, maxima = htk.segmentation.nuclear.max_clustering(
      im_log_max, im_fgnd_mask, local_max_search_radius)

  # filter out small objects
  min_nucleus_area = 80

  im_nuclei_seg_mask = htk.segmentation.label.area_open(
      im_nuclei_seg_mask, min_nucleus_area).astype(np.int64)

  # compute nuclei properties
  objProps = skimage.measure.regionprops(im_nuclei_seg_mask)
  return len(objProps)

import copy
def center_cropping_image(read_img):
  mid_pointy=read_img.shape[0]//2;
  mid_pointx=read_img.shape[1]//2;
  xshape=read_img.shape[1]
  yshape=read_img.shape[0]
  return read_img[max(0,mid_pointy-512):min(yshape,mid_pointy+512),max(0,mid_pointx-512):min(xshape,mid_pointx+512),:]
def windowing_image(read_img):
  assert read_img.shape[0]==1024 and read_img.shape[1]==1024
  L=np.zeros((4,4,1))
  row=0
  col=0
  for i in range(0,512,128):
    for j in range(0,512,128):
      L[row,col,0]=get_nuclei_den(read_img[i:i+512,j:j+512,:])
      if col+1==4:
        col=0;
        row+=1;
      else:
        col+=1;
  return L
def create_heat(path):
    read_img=copy.deepcopy(path)
    xshape=read_img.shape[1]
    yshape=read_img.shape[0]
    read_image=copy.deepcopy(path)
    if read_img.shape[0]<1024 or read_img.shape[1]<1024:
      tmp_op=np.zeros((max(read_img.shape[0],1024),max(read_img.shape[1],1024),3))
      tmp_op.fill(255)
      tmp_op[:read_img.shape[0],:read_img.shape[1],:]=read_img
      read_img=tmp_op
    read_img=center_cropping_image(read_img)
    heatmap=windowing_image(read_img)
    return heatmap
class CreatePatches(Dataset):
  def __init__(self,path,transforms=None):
    self.path=path
    self.transforms=transforms
  def __len__(self):
    return self.path.__len__()
  def __getitem__(self,indx):
    img=self.path[indx][0]
    labl=self.path[indx][1]
    inp2=create_heat(imread(img))
    #inp1=create_heat(imread(img))
    # if 'DCIS' in img and inp2>410 and (op.shape[0]<2500 or op.shape[1]<2500):
    #   inp2=max(inp2,589.0);
    inp=torch.from_numpy(inp2.reshape(1,4,4).astype(np.float32))
    label=torch.tensor([labl],dtype=torch.float32)
    return inp,label
dataset=CreatePatches(List_paths[:20])
Train=DataLoader(dataset,shuffle=False,batch_size=4,drop_last=True)

class SmallConvNet(nn.Module):
  def __init__(self,shape=4):
    super(SmallConvNet,self).__init__()
    self.shape=shape
    self.l1=nn.Conv2d(1,64,kernel_size=(3,3),padding='same')
    self.r=nn.ReLU(inplace=True)
    self.l2=nn.Conv2d(64,128,kernel_size=(3,3),padding='same')
    self.l3=nn.MaxPool2d(kernel_size=2)
    self.l4=nn.Conv2d(128,32,kernel_size=3,padding='same')
    self.l5=nn.Flatten()
    self.linear=nn.Sequential(
          nn.Linear(2*2*32,64),
          nn.ReLU(inplace=True),
          nn.Linear(64,128),
          nn.ReLU(inplace=True),
          nn.Linear(128,64),
          nn.ReLU(inplace=True),
          nn.Linear(64,1)
      )
  def forward(self,x):
    x=self.r(self.l1(x))
    x=self.l3(x)
    x=self.r(self.l2(x))
    x=self.l3(x)
    x=self.r(self.l4(x))
    x=self.l5(x)
    return self.linear(x)
model=SmallConvNet()
model.to(dev)

for x,y in Train:
  print(x.shape,x,y)

import json
optimizer=torch.optim.Adam(model.parameters())
loss_fn=nn.BCEWithLogitsLoss()
epochs=25
for e in range(epochs):
  model.train()
  L=0
  S=0;
  fn=0
  fp=0;
  tp=0;
  tn=0;
  pbar=tqdm.tqdm(Train,desc='Training');
  for x,y in pbar:
    optimizer.zero_grad()
    x,y=x.to(dev),y.to(dev)
    pred=model(x)
    loss=loss_fn(pred,y)
    loss.backward()
    optimizer.step()
    L+=loss.item()
    S+=1;
    for i in range(len(pred)):
      if int(y[i][0])==1:
        if pred[i][0]>=0.59:
          tp+=1
        else:
          fn+=1
      else:
        if pred[i][0]>=0.59:
          fp+=1;
        else:
          tn+=1;
  try:
    print(f'Epoch[{e+1}/{epochs}] Loss: {L/S} Acc: {(tp+tn)/(tp+tn+fn+fp)} Percision {tp/(fp+tp)} Recall: {tp/(fn+tp)} F1 Score:{(2*(tp/(fp+tp))*(tp/(fn+tp)))/((tp/(fp+tp))+(tp/(fn+tp)))}');
  except:
    print("Error")