import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import matplotlib.pyplot as plt
from PIL import Image
import cv2
import numpy as np
from nerf2D import Positional_Encoding
from torch_network import Net
import random
import torchmetrics
import seaborn as sns

def get_data(image, encoding, L=10, batch_size=2048, RFF=False):

    # Get the training image
    trainimg= image
    trainimg = trainimg / 255.0  
    H, W, C = trainimg.shape

    # Get the encoding
    PE = Positional_Encoding(trainimg, encoding, training=True)
    inp_batch, inp_target, ind_vals = PE.get_dataset(L, RFF=False)

    inp_batch, inp_target = torch.Tensor(inp_batch), torch.Tensor(inp_target)
    inp_batch, inp_target = inp_batch.to('cuda:0'), inp_target.to('cuda:0')

    # create batches to track batch loss and show it is more stable due to gabor encoding
    full_batches = []
    batches = []
    batch_targets = []

    random_batches = []
    random_targets = []
    # make sure to choose one which can be evenly divided by 65536
    for i in range(H*W):
        full_batches.append((inp_batch[i], inp_target[i]))

    random.shuffle(full_batches)
    for i in range(H*W):
        batches.append(full_batches[i][0])
        batch_targets.append(full_batches[i][1])

    batches = torch.stack(batches, dim=0)
    batch_targets = torch.stack(batch_targets, dim=0)
    for i in range(0, H*W, batch_size):
        random_batches.append(batches[i:i+batch_size])
        random_targets.append(batch_targets[i:i+batch_size])

    random_batches = torch.stack(random_batches, dim=0)
    random_targets = torch.stack(random_targets, dim=0)

    return random_batches, random_targets

model_raw = Net(2, 128).to('cuda:0')
optim_raw = torch.optim.Adam(model_raw.parameters(), lr=.001)
model_pe = Net(32, 128).to('cuda:0')
optim_pe = torch.optim.Adam(model_pe.parameters(), lr=.001)
model_gabor = Net(176, 128).to('cuda:0')
optim_gabor = torch.optim.Adam(model_gabor.parameters(), lr=.001)
criterion = nn.MSELoss()
epochs = 10

# compute gradients individually for each, not sure best way to do this yet

#im = Image.open(f'dataset/fractal.jpg')
#im2arr = np.array(im)
im2arr = np.random.randint(0, 255, (28, 28, 3))

# Get the encoding raw_xy
train_inp_batch, train_inp_target = get_data(image=im2arr, encoding='raw_xy', L=0, batch_size=28)
inp_batch, inp_target = get_data(image=im2arr, encoding='raw_xy', L=0, batch_size=1)

raw_grad_similarities = []
losses = []
for epoch in range(epochs):
    raw_gradients = torch.empty([784, 17283]).to('cuda:0')
    running_loss = 0
    for i, pixel in enumerate(train_inp_batch):
        optim_raw.zero_grad()
        output = model_raw(pixel)
        loss = criterion(output, train_inp_target[i])
        loss.backward()
        optim_raw.step()
    for i, pixel in enumerate(inp_batch):
        optim_raw.zero_grad()
        output = model_raw(pixel)
        loss = criterion(output, inp_target[i])
        running_loss += loss.item()
        loss.backward()
        grads = torch.cat([torch.flatten(model_raw.l1.weight.grad), torch.flatten(model_raw.l2.weight.grad), torch.flatten(model_raw.l3.weight.grad), torch.flatten(model_raw.l1.bias.grad), torch.flatten(model_raw.l2.bias.grad), torch.flatten(model_raw.l3.bias.grad)])
        raw_gradients[i] = grads
    running_loss /= inp_batch.shape[0]
    losses.append(running_loss)
    # get inner products of gradients for raw xy
    for i in range(raw_gradients.shape[0]):
        for j in range(i, raw_gradients.shape[0]):
            if i != j:
                #print(torchmetrics.functional.pairwise_cosine_similarity(raw_gradients[i].unsqueeze(dim=0), raw_gradients[j].unsqueeze(dim=0)).cpu().item())
                raw_grad_similarities.append(torch.flatten(torchmetrics.functional.pairwise_cosine_similarity(raw_gradients[i].unsqueeze(dim=0), raw_gradients[j].unsqueeze(dim=0))).cpu())

# Get the encoding sin cos
train_inp_batch, train_inp_target = get_data(image=im2arr, encoding='sin_cos', L=8, batch_size=28)
inp_batch, inp_target = get_data(image=im2arr, encoding='sin_cos', L=8, batch_size=1)

sin_cos_grad_similarity = []
pe_losses = []
for epoch in range(epochs):
    pe_gradients = torch.empty([784, 21123]).to('cuda:0')
    running_loss = 0
    for i, pixel in enumerate(train_inp_batch):
        optim_pe.zero_grad()
        output = model_pe(pixel)
        loss = criterion(output, train_inp_target[i])
        loss.backward()
        optim_pe.step()
    for i, pixel in enumerate(inp_batch):
        optim_pe.zero_grad()
        output = model_pe(pixel)
        loss = criterion(output, inp_target[i])
        running_loss += loss.item()
        loss.backward()
        grads = torch.cat([torch.flatten(model_pe.l1.weight.grad), torch.flatten(model_pe.l2.weight.grad), torch.flatten(model_pe.l3.weight.grad), torch.flatten(model_pe.l1.bias.grad), torch.flatten(model_pe.l2.bias.grad), torch.flatten(model_pe.l3.bias.grad)])
        pe_gradients[i] = grads
    running_loss /= inp_batch.shape[0]
    pe_losses.append(running_loss)
    # get inner products of gradients for sin_cos
    for i in range(pe_gradients.shape[0]):
        for j in range(i, pe_gradients.shape[0]):
            if i != j:
                sin_cos_grad_similarity.append(torch.flatten(torchmetrics.functional.pairwise_cosine_similarity(pe_gradients[i].unsqueeze(dim=0), pe_gradients[j].unsqueeze(dim=0)).cpu()))

sns.kdeplot(data=torch.cat(sin_cos_grad_similarity).cpu(), fill=True)
sns.kdeplot(data=torch.cat(raw_grad_similarities).cpu(), fill=True)
plt.show()

plt.plot(losses)
plt.plot(pe_losses)
plt.show()

'''
# Get the encoding gabor
inp_batch, inp_target = get_data(image=im2arr, encoding='gauss', L=8, batch_size=2048)

gabor_gradients = []
for epoch in range(5):
    for i, pixel in enumerate(inp_batch):
        optim_gabor.zero_grad()
        output = model_gabor(pixel)
        loss = criterion(output, inp_target[i])
        loss.backward()
        if epoch < 4:
            optim_gabor.step()
        if epoch == 4:
            grads = torch.cat([torch.flatten(model_gabor.l1.weight.grad), torch.flatten(model_gabor.l2.weight.grad), torch.flatten(model_gabor.l3.weight.grad)])
            gabor_gradients.append(grads)

gabor_grad_kernel = []
# get inner products of gradients for gabor
for i in range(np.shape(inp_batch)[0]):
    for j in range(i, np.shape(inp_batch)[0]):
        if i != j:
            gabor_grad_kernel.append(torchmetrics.functional.pairwise_cosine_similarity(gabor_gradients[i].unsqueeze(dim=0), gabor_gradients[j].unsqueeze(dim=0)))

lowest = min(gabor_grad_kernel)
print(lowest)
'''