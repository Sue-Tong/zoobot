import logging

import torch
import torchvision


def get_resnet(input_channels, use_imagenet_weights=False, include_top=False, **ignored_kwargs):  # only colour supported
    # https://pytorch.org/vision/stable/_modules/torchvision/models/resnet.html#resnet50 see here - could paste and adapt for greyscale if needed
    if not input_channels == 3:
        raise ValueError('torchvision resnet only supports color (without altering their code) - input_channels must be 3, not {}'.format(input_channels))
    assert include_top == False
    model_with_head = torchvision.models.resnet50(pretrained=use_imagenet_weights, progress=False)

    logging.warning(f'get_resnet passed additional keyword arguments which could not be interpreted - these will be ignored. {ignored_kwargs}')

    modules = list(model_with_head.children())[:-1] # last layer is the linear layer (drop), penultimate is adaptive pooling (keep)
    modules.append(torch.nn.Flatten(1))

    model = torch.nn.Sequential(*modules)  
    # print([x for x in model.children()])
    # print(model)
    return model
    

if __name__ == '__main__':

    # debugging only

    import numpy as np

    from zoobot.pytorch.training import losses
    from galaxy_datasets.shared import label_metadata
    from zoobot.shared import schemas
    from zoobot.pytorch.estimators import define_model

    channels = 3

    question_answer_pairs = label_metadata.decals_all_campaigns_ortho_pairs
    dependencies = label_metadata.decals_ortho_dependencies
    schema = schemas.Schema(question_answer_pairs, dependencies)

    loss_func = losses.calculate_multiquestion_loss

    model = define_model.ZoobotModel(schema=schema, loss=loss_func, channels=channels, get_architecture=get_resnet, representation_dim=2048)

    x = torch.from_numpy(np.random.rand(16, channels, 224, 224)).float()
    # print(model(x))
    print(model(x).shape)
