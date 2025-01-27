import logging
import time
import datetime
from typing import List
import numpy as np
import pandas as pd
import torch
import pytorch_lightning as pl

from zoobot.shared import save_predictions
from galaxy_datasets.pytorch.galaxy_datamodule import GalaxyDataModule


def predict(catalog: pd.DataFrame, model: pl.LightningModule, n_samples: int, label_cols: List, save_loc: str, datamodule_kwargs={}, trainer_kwargs={}):
    """
    Use trained model to make predictions on a catalog of galaxies.

    Args:
        catalog (pd.DataFrame): catalog of galaxies to make predictions on. Must include `file_loc` and `id_str` columns.
        model (pl.LightningModule): with which to make predictions. Probably ZoobotTree, FinetuneableZoobotClassifier, FinetuneableZoobotTree, or ZoobotEncoder.
        n_samples (int): num. of forward passes to make per galaxy. Useful to marginalise over augmentations/test-time dropout.
        label_cols (List): Names for prediction columns. Only for your convenience - has no effect on predictions.
        save_loc (str): desired name of file recording the predictions
        datamodule_kwargs (dict, optional): Passed to GalaxyDataModule. Use to e.g. add custom augmentations. Defaults to {}.
        trainer_kwargs (dict, optional): Passed to pl.Trainer. Defaults to {}.
    """

    image_id_strs = list(catalog['id_str'].astype(str))

    predict_datamodule = GalaxyDataModule(
        label_cols=None,  # not using label_cols to load labels, we're only using it to name our predictions
        predict_catalog=catalog,  # no need to specify the other catalogs
        # will use the default transforms unless overridden with datamodule_kwargs
        # 
        **datamodule_kwargs  # e.g. batch_size, resize_size, crop_scale_bounds, etc.
    )
    # with this stage arg, will only use predict_catalog 
    # crucial to specify the stage, or will error (as missing other catalogs)
    predict_datamodule.setup(stage='predict')  
    for images in predict_datamodule.predict_dataloader():
        logging.info(images)
        logging.info(images.shape)


    # set up trainer (again)
    trainer = pl.Trainer(
        max_epochs=-1,  # does nothing in this context, suppresses warning
        inference_mode=True,  # no grads needed
        **trainer_kwargs  # e.g. gpus
    )

    # from here, very similar to tensorflow version - could potentially refactor

    logging.info('Beginning predictions')
    start = datetime.datetime.fromtimestamp(time.time())
    logging.info('Starting at: {}'.format(start.strftime('%Y-%m-%d %H:%M:%S')))

    logging.info(len(trainer.predict(model, predict_datamodule)))

    # trainer.predict gives list of tensors, each tensor being predictions for a batch. Concat on axis 0.
    # range(n_samples) list comprehension repeats this, for dropout-permuted predictions. Stack to create new last axis.
    # final shape (n_galaxies, n_answers, n_samples)
    predictions = torch.stack([torch.concat(trainer.predict(model, predict_datamodule), dim=0) for n in range(n_samples)], dim=-1).numpy()
    logging.info('Predictions complete - {}'.format(predictions.shape))
    
    # compute losses
    y_true = torch.tensor(catalog['ring_fraction'])
    loss = cross_entropy_loss(torch.tensor(y_pred.squeeze()), y_true)
    
#     losses = []
#     y_trues = []  # to store the 1D class labels
#     for batch in predict_datamodule.predict_dataloader():
#         with torch.no_grad():
#             output = model(batch)
#         y_pred = torch.softmax(output, dim=-1)
#         y_true = batch["target"]
#         y_trues.append(y_true.view(-1))  # flatten to 1D tensor
#         loss = cross_entropy_loss(y_pred, y_true.view(-1))  # convert y_true to 1D tensor
#         logging.info("loss")
#         logging.info(loss)
#         losses.append(loss.cpu().numpy())
#     losses = np.concatenate(losses)
#     y_trues = torch.cat(y_trues)  # combine into single 1D tensor

    logging.info(f'Saving predictions to {save_loc}')

    if save_loc.endswith('.csv'):      # save as pandas df
        save_predictions.predictions_to_csv(predictions, image_id_strs, label_cols, save_loc,losses=losses)
    elif save_loc.endswith('.hdf5'):
        save_predictions.predictions_to_hdf5(predictions, image_id_strs, label_cols, save_loc,losses=losses)
    else:
        logging.warning('Save format of {} not recognised - assuming csv'.format(save_loc))
        save_predictions.predictions_to_csv(predictions, image_id_strs, label_cols, save_loclosses=losses)

    logging.info(f'Predictions saved to {save_loc}')

    end = datetime.datetime.fromtimestamp(time.time())
    logging.info('Completed at: {}'.format(end.strftime('%Y-%m-%d %H:%M:%S')))
    logging.info('Time elapsed: {}'.format(end - start))
