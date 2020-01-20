import torch
import time, argparse
from datetime import datetime
import numpy as np
from loaders import FLADataset
from networks import *
from losses import *
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
import tqdm
from helpers_train_test import train_test_model



def main():
    parser = argparse.ArgumentParser(description='KITTI relative odometry experiment')
    parser.add_argument('--epochs', type=int, default=10)

    parser.add_argument('--batch_size_test', type=int, default=64)
    parser.add_argument('--batch_size_train', type=int, default=32)

    parser.add_argument('--cuda', action='store_true', default=False)
    parser.add_argument('--num_workers', type=int, default=4)
    parser.add_argument('--megalith', action='store_true', default=False)

    parser.add_argument('--double', action='store_true', default=False)
    parser.add_argument('--optical_flow', action='store_true', default=False)
    parser.add_argument('--batchnorm', action='store_true', default=False)
    
    parser.add_argument('--unit_frob', action='store_true', default=False)
    parser.add_argument('--save_model', action='store_true', default=False)
    parser.add_argument('--enforce_psd', action='store_true', default=False)

    parser.add_argument('--model', choices=['A_sym', '6D', 'quat'], default='A_sym')

    #Randomly select within this range
    parser.add_argument('--lr', type=float, default=5e-4)


    args = parser.parse_args()
    print(args)

    #Float or Double?
    tensor_type = torch.float


    device = torch.device('cuda:0') if args.cuda else torch.device('cpu')
    tensor_type = torch.double if args.double else torch.float

    normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                     std=[0.229, 0.224, 0.225])

    transform = transforms.Compose([
            torchvision.transforms.Resize(224),
            torchvision.transforms.CenterCrop(224),
            transforms.ToTensor(),
            normalize,
    ])
    # seqs_base_path = '/media/m2-drive/datasets/KITTI/single_files'
    # if args.megalith:
    #     seqs_base_path = '/media/datasets/KITTI/single_files'

    #Monolith
    image_dir = '/media/m2-drive/datasets/fla/2020.01.14_rss2020_data/2017_05_10_10_18_40_fla-19/xtion'
    pose_dir = '/media/m2-drive/datasets/fla/2020.01.14_rss2020_data/2017_05_10_10_18_40_fla-19/pose'
    #Indoor is 6000-7600 absolute
    #approximately 1730-4330 relative
    train_loader = DataLoader(FLADataset(image_dir=image_dir, pose_dir=pose_dir, select_idx=[1800, 4000], transform=transform),
                            batch_size=args.batch_size_train, pin_memory=False,
                            shuffle=True, num_workers=args.num_workers, drop_last=False)

    valid_loader = DataLoader(FLADataset(image_dir=image_dir, pose_dir=pose_dir, select_idx=[4000, 4300], transform=transform),
                            batch_size=args.batch_size_test, pin_memory=False,
                            shuffle=False, num_workers=args.num_workers, drop_last=False)
    #Train and test with new representation
    dim_in = 2 if args.optical_flow else 6

    
    if args.model == 'A_sym':
        print('==============Using A (Sym) MODEL====================')
        model = QuatFlowNet(enforce_psd=args.enforce_psd, unit_frob_norm=args.unit_frob, dim_in=dim_in, batchnorm=args.batchnorm).to(device=device, dtype=tensor_type)
        train_loader.dataset.rotmat_targets = False
        valid_loader.dataset.rotmat_targets = False
        loss_fn = quat_chordal_squared_loss
        (train_stats, test_stats) = train_test_model(args, loss_fn, model, train_loader, valid_loader, tensorboard_output=False)

    elif args.model == '6D':
        print('==========TRAINING DIRECT 6D ROTMAT MODEL============')
        model = RotMat6DFlowNet(dim_in=dim_in, batchnorm=args.batchnorm).to(device=device, dtype=tensor_type)
        train_loader.dataset.rotmat_targets = True
        valid_loader.dataset.rotmat_targets = True
        loss_fn = rotmat_frob_squared_norm_loss
        (train_stats, test_stats) = train_test_model(args, loss_fn, model, train_loader, valid_loader, tensorboard_output=False)

    elif args.model == 'quat':
        print('=========TRAINING DIRECT QUAT MODEL==================')
        model = BasicCNN(dim_in=dim_in, dim_out=4, normalize_output=True, batchnorm=args.batchnorm).to(device=device, dtype=tensor_type)
        train_loader.dataset.rotmat_targets = False
        valid_loader.dataset.rotmat_targets = False
        loss_fn = quat_chordal_squared_loss
        (train_stats, test_stats) = train_test_model(args, loss_fn, model, train_loader, valid_loader, tensorboard_output=False)

    if args.save_model:
        saved_data_file_name = 'fla_model_{}_seq_{}_{}'.format(args.model, args.seq, datetime.now().strftime("%m-%d-%Y-%H-%M-%S"))
        full_saved_path = 'saved_data/fla/{}.pt'.format(saved_data_file_name)
        torch.save({
                'model_type': args.model,
                'model': model.state_dict(),
                'train_stats_rep': train_stats.detach().cpu(),
                'test_stats_rep': test_stats.detach().cpu(),
                'args': args,
            }, full_saved_path)

        print('Saved data to {}.'.format(full_saved_path))

if __name__=='__main__':
    main()