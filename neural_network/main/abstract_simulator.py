from typing import List
import pandas as pd

from neural_network.util import Partitioner
from neural_network.util import WeightedPartitioner
from neural_network.functions import Loss
from neural_network.components import Network

from .plotter import Plotter


class AbstractSimulator:
    """Base class for trainer, tester and validator
    """

    def __init__(self, network: Network, data: pd.DataFrame, batch_size: int,
                 weighted: bool = False, classification: bool = True):
        """Constructor method

        Parameters
        ----------
        network : Network
            The neural network to train
        data : pd.DataFrame
            All the data for the `Network`
        batch_size : int
            The number of datapoints used in each epoch
        weighted : bool
            If `True` then we use the WeightedPartitioner, otherwise we use
            the standard Partitioner
        classification : bool
            If `True` then we are classifying, otherwise it will be regression
        """
        self._network = network
        data = data.copy()
        # Ensure that number of input nodes equals number of features
        n = len(data.columns) - 1
        m = network.get_neuron_counts()[0]
        if m != n:
            raise ValueError(f"Number of features must match number of "
                             f"initial neurons (features = {n}, initial "
                             f"neurons = {m})")

        # Renaming of columns
        data.columns = [f'x_{i + 1}' for i in range(n)] + ['y']

        # Save the category names to be used for plots and output data
        self._category_names = sorted(list(set(data['y'])))

        # Ensure that number of network output neurons equals the number of
        # classes in the dataframe
        num_classes = len(self._category_names)
        num_outputs = network.get_neuron_counts()[-1]
        if num_outputs < num_classes:
            raise ValueError(f"The number of output neurons in the network "
                             f"({num_outputs}) is less than the number of "
                             f"classes in the dataframe ({num_classes})")

        # Ensure that batch_size is not too big
        if batch_size > len(data):
            raise ValueError("Batch size must be smaller than number of "
                             "datapoints")

        # Change the category names to integers from 0 to num_classes - 1 for
        # the numerical calculations, but save the category names for reference
        # in plots.
        data['y_hat'] = [0] * len(data)
        self._categorical_data = data
        numerical_data = data.replace({'y': {self._category_names[i]: i
                                             for i in range(num_classes)}})
        self._data = numerical_data
        self._batch_size = batch_size
        self._classification = classification
        self._loss = Loss()
        if weighted:
            self._partitioner = WeightedPartitioner(len(data), batch_size,
                                                    numerical_data)
        else:
            self._partitioner = Partitioner(len(data), batch_size)

    def forward_pass_one_batch(self, batch_ids: List[int]) -> float:
        """Performs the forward pass for one batch of the data.

        Parameters
        ----------
        batch_ids : List[int]
            The random list of ids for the current batch

        Returns
        -------
        float
            The total loss of the batch (to keep track)
        """
        total_loss = 0
        for i in batch_ids:
            labelled_point = self._data.loc[i].to_numpy()
            x, y = labelled_point[:-2], int(labelled_point[-2])
            # Do the forward pass and save the predicted value to the df
            softmax_vector = self._network.forward_pass_one_datapoint(x)
            total_loss += self._loss(softmax_vector, y)
            self._data.at[i, 'y_hat'] = max(range(len(softmax_vector)),
                                            key=softmax_vector.__getitem__)
            self.store_gradients(i)
        # Return the total loss for this batch
        return total_loss

    def run(self):
        """Performs training/validation/testing
        """
        raise NotImplementedError("Cannot call from base class")

    def store_gradients(self, batch_id: int):
        """To be overridden by subclasses.

        Parameters
        ----------
        batch_id : id of the current batch
        """
        return

    def _update_categorical_dataframe(self):
        """Update the categorical dataframe with y_hat data but using the
        original categories from the data - to be used for plotting and
        outputs to the user. Note that this method will be called after
        training/testing/validation is complete so that the y_hat values are
        fully updated.
        """
        names = self._category_names
        self._categorical_data['y_hat'] = \
            list(self._data.replace({'y_hat':
                                    {i: names[i] for i in range(len(names))}})
                 ['y_hat'])

    def abs_generate_scatter(self, phase: str = 'training', title: str = ''):
        """Creates scatter plot from the data and their predicted values. We
        use the categories the user provided with the data instead of arbitrary
        integer classes.

        Parameters
        ----------
        phase : str
            The phase of learning
        title : str
            An optional title to append to the plot
        """
        Plotter.plot_predictions(self._categorical_data, phase, title)
