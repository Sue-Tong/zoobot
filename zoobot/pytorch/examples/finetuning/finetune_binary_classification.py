import logging
import os

from zoobot.pytorch.training import finetune
from galaxy_datasets import demo_rings
from galaxy_datasets.pytorch.galaxy_datamodule import GalaxyDataModule


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)

    zoobot_dir = '/home/walml/repos/zoobot'  # TODO set to directory where you cloned Zoobot

    # load in catalogs of images and labels to finetune on
    # each catalog should be a dataframe with columns of "id_str", "file_loc", and any labels
    # here I'm using galaxy-datasets to download some premade data - check it out for examples
    data_dir = '/home/walml/repos/galaxy-datasets/roots/demo_rings'
    train_catalog, label_cols = demo_rings(root=data_dir, download=True, train=True)
    test_catalog, _ = demo_rings(root=data_dir, download=True, train=False)


    # wondering about "label_cols"? 
    # This is a list of catalog columns which should be used as labels
    # Here:   label_cols = ['ring']
    # For binary classification, the label column should have binary (0 or 1) labels for your classes
    # To support more complicated labels, Zoobot expects a list of columns. A list with one element works fine.
   
    # load a pretrained checkpoint saved here
    checkpoint_loc = os.path.join(zoobot_dir, 'data/pretrained_models/temp/dr5_py_gr_2270/checkpoints/epoch=360-step=231762.ckpt')
    
    # save the finetuning results here
    save_dir = os.path.join(zoobot_dir, 'results/pytorch/finetune/finetune_binary_classification')

    datamodule = GalaxyDataModule(
      label_cols=label_cols,
      catalog=train_catalog,
      batch_size=32
    )

    # datamodule.setup()
    # for images, labels in datamodule.train_dataloader():
    #   print(images.shape)
    #   print(labels.shape)
    #   exit()

    config = {
        'trainer': {
            'devices': 1,
            'accelerator': 'cpu'
        },
        'finetune': {
            'encoder_dim': 1280,
            'label_dim': 2,
            'n_epochs': 100,
            'n_layers': 2,
            'label_mode': 'classification',
            'learning_rate': 3e-4,
            'lr_decay': 0.75,
            'dropout_prob': 0.5,
            'prog_bar': True
        }
    }

    encoder = finetune.load_encoder(checkpoint_loc)

    _finetuned_model, best_checkpoint_path = finetune.run_finetuning(config, encoder, datamodule, save_dir, logger=None)

    # can now use this model or saved checkpoint to make predictions on new data. Well done!

    # pretending we want to load from scratch:
    finetuned_model = finetune.FinetunedZoobotLightningModule.load_from_checkpoint(best_checkpoint_path)

    # or using the convenient zoobot function
    from zoobot.pytorch.predictions import predict_on_catalog

    predict_on_catalog.predict(
      test_catalog,
      finetuned_model,
      n_samples=1,
      label_cols=label_cols,
      save_loc=os.path.join(save_dir, 'finetuned_predictions.csv')
      # trainer_kwargs={'accelerator': 'gpu'}
    )



    """
    Under the hood, this is essentially doing:

    import pytorch_lightning as pl
    predict_trainer = pl.Trainer(devices=1, max_epochs=-1)
    predict_datamodule = GalaxyDataModule(
      label_cols=None,  # important, else you will get "conv2d() received an invalid combination of arguments"
      predict_catalog=test_catalog,
      batch_size=32
    )
    preds = predict_trainer.predict(finetuned_model, predict_datamodule)
    print(preds)
    """