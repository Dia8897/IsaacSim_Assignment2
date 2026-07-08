import numpy as np

arr = np.load(r"C:\Users\User\Desktop\Assignment2\IsaacSim_Assignment2\output\Replicator\semantic\000000.npy")

print("dtype:", arr.dtype)
print("shape:", arr.shape)
print("unique values:", np.unique(arr))