import torch

# CUDA 확인
cuda_available = torch.cuda.is_available()
print(f"CUDA available: {cuda_available}")

# cuDNN 확인
cudnn_available = torch.backends.cudnn.is_available()
print(f"cuDNN available: {cudnn_available}")

# NCCL 확인
nccl_available = torch.distributed.is_nccl_available()
print(f"NCCL available: {nccl_available}")