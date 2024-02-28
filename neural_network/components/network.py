from typing import List
import math
import random

import numpy as np

from neural_network.functions import TransferFunction
from neural_network.functions import ReLU
from neural_network.functions import Softmax

from .neuron import Neuron
from .edge import Edge
from .layer import Layer


class Network:
    """Class to represent the whole `Network`
    """

    def __init__(self, num_features: int, num_hidden_layers: int,
                 neuron_counts: List[int], leak: float = 0.01,
                 learning_rate: float = 0.01, num_classes: int = 2,
                 adaptive: bool = False, gamma: float = 0.9,
                 he_weights: bool = False):
        """Constructor method

        Parameters
        ----------
        num_features : int
            The number of features for the network
        num_hidden_layers : int
            The total number of hidden `Layers` in the `Network`
        neuron_counts : List[int]
            A list of numbers of `Neurons` for each hidden `Layer`
        leak : float
            The leak rate of LeakyReLU
        learning_rate : float
            The learning rate of the network
        num_classes : int
            The number of classes for the classification task
        adaptive : bool
            Whether we wish to have an adaptive learning rate or not
        gamma : float
            The adaptive learning rate parameter
        he_weights : bool
            Whether we wish to initialise the weights according to He or not
        """
        if not num_hidden_layers == len(neuron_counts):
            raise ValueError(f"neuron_counts ({len(neuron_counts)}) must have "
                             f"a length equal to num_hidden_layers "
                             f"({num_hidden_layers})")
        self._num_features = num_features
        self._num_hidden_layers = num_hidden_layers
        self._neuron_counts = neuron_counts
        self._input_layer = Layer(0, num_features)
        self._hidden_layers = [Layer(i, neuron_counts[i - 1])
                               for i in range(1, num_hidden_layers + 1)]
        self._output_layer = Layer(num_hidden_layers + 1, num_classes)
        self._softmax_layer = Layer(num_hidden_layers + 2, num_classes)
        self._main_layers = ([self._input_layer] + self._hidden_layers
                             + [self._output_layer])
        self._edges = []
        for i, left_layer in enumerate(self._main_layers[:-1]):
            right_layer = self._main_layers[i + 1]
            layer_list = []
            for right_neuron in right_layer.get_neurons():
                edge_list = [Edge(left_neuron, right_neuron)
                             for left_neuron in left_layer.get_neurons()]
                layer_list.append(edge_list)
                if he_weights:
                    n = len(left_layer)
                    for edge in edge_list:
                        edge.set_weight(random.gauss(0.0,
                                                     math.sqrt(2 / n)))
            self._edges.append(layer_list)
        self._softmax_edges = [Edge(self._output_layer.get_neurons()[i],
                                    self._softmax_layer.get_neurons()[i])
                               for i in range(num_classes)]
        self._transfer = TransferFunction()
        self._relu = ReLU(leak)
        self._softmax = Softmax()
        self._learning_rate = learning_rate
        self._adaptive = adaptive
        self._gamma = gamma

    def forward_pass_one_datapoint(self, x: np.array) -> List[float]:
        """Performs a forward pass for one datapoint, excluding the ground
        truth value. This method returns the predicted value in the final
        neuron in the output layer.

        Parameters
        ----------
        x : np.array
            The input value, with all features

        Returns
        -------
        List[float]
            The softmax probabilities of each class
        """
        if not len(x) == len(self._input_layer):
            raise ValueError(f"Number of features must match the number of "
                             f"neurons in the input layer ({len(x)} != "
                             f"{len(self._input_layer)})")

        # Input layer
        input_neurons = self._input_layer.get_neurons()
        for j, neuron in enumerate(input_neurons):
            neuron.set_value(x[j])

        # Hidden layers and output layer
        for left_layer in self._main_layers[:-1]:
            right_layer = self._main_layers[left_layer.get_id() + 1]
            for right_neuron in right_layer.get_neurons():

                # Calculates the desired values for each neuron
                self._propagate_value_forward(left_layer, right_neuron)

        # Output -> softmax layer
        # Calculates all values in the softmax_layer
        softmax_vector = self._propagate_softmax_layer()
        return softmax_vector

    def _propagate_value_forward(self, left_layer: Layer,
                                 right_neuron: Neuron):
        """Given a `left_layer` and a `right_neuron`, this calculates the
        activation function and value from the `left_layer` and propagates
        this value to the `right_neuron`

        Parameters
        ----------
        left_layer : Layer
            The current `left_layer` in forward propagation
        right_neuron : Neuron
            The current `right_neuron` in forward propagation
        """
        left_neurons = left_layer.get_neurons()
        i, j = right_neuron.get_id()

        # All edges connecting the left_layer to the right_neuron
        edges = self._edges[i - 1][j]

        # Lists of values and weights, with the bias
        o_list = [neuron.get_value() for neuron in left_neurons]
        w_list = [edge.get_weight() for edge in edges]
        bias = right_neuron.get_bias()
        z = self._transfer(o_list, w_list + [bias])

        # Use ReLU to find the value for the right_neuron
        right_neuron.set_value(self._relu(z))

    def _propagate_softmax_layer(self) -> List[float]:
        """Completes a forward pass for one datapoint by transferring all
        values from the output layer into softmax probabilities

        Returns
        -------
        List[float]
            The `List` of softmax probabilities
        """
        values = [neuron.get_value()
                  for neuron in self._output_layer.get_neurons()]
        self._softmax.normalisation(values)
        softmax_neurons = self._softmax_layer.get_neurons()
        softmax_vector = []
        for j, value in enumerate(values):
            softmax = self._softmax(value)
            softmax_vector.append(softmax)
            softmax_neurons[j].set_value(softmax)

        return softmax_vector

    def store_gradient_of_loss(self, edge: Edge, target: int, first: bool):
        """Calculates the gradient of the loss function with respect to one
        weight (assigned to the edge) based on the values at edges of future
        layers. One part of the back propagation process.

        edge : Edge
            The `Edge` containing the weight we are interested in
        target : int
            The target value for the final output node for this specific
            datapoint
        first : bool
            Determines whether we find the bias gradient or not
        """
        left_layer_index = edge.get_id()[0]
        right_neuron = edge.get_right_neuron()

        # Value of left neuron and right neuron
        o_left = edge.get_left_neuron().get_value()
        o_right = right_neuron.get_value()

        # Constant (either +1 or -self._leak)
        relu_grad = self._relu.gradient(o_right)
        right_index, row = right_neuron.get_id()

        # Softmax layer
        if left_layer_index == self._num_hidden_layers + 1:
            edge.loss_gradients.append(o_right - int(row == target))

        # Output layer
        elif left_layer_index == self._num_hidden_layers:
            delta = self._softmax_edges[row].loss_gradients[-1] * relu_grad
            edge.loss_gradients.append(o_left * delta)
            if first:
                right_neuron.bias_gradients.append(delta)

        # Hidden layers
        else:
            next_layer = self._main_layers[right_index + 1]
            next_edges = [self._edges[right_index][j][row]
                          for j in range(len(next_layer))]
            factor = sum([new_edge.get_weight() * new_edge.loss_gradients[-1]
                          for new_edge in next_edges])
            edge.loss_gradients.append(o_left * factor * relu_grad)
            if first:
                right_neuron.bias_gradients.append(factor * relu_grad)

    def back_propagate_weight(self, edge: Edge):
        """Uses the loss gradients of all datapoints (for this specific edge)
        to perform gradient descent and calculate a new weight for this edge.

        edge : Edge
            The `Edge` whose weight we are interested in updating
        """
        current_weight = edge.get_weight()
        batch_size = len(edge.loss_gradients)
        avg_loss_gradient = sum(edge.loss_gradients) / batch_size
        if self._adaptive:
            velocity = (self._gamma * edge.get_velocity()
                        + self._learning_rate * avg_loss_gradient)
            edge.set_weight(current_weight - velocity)
            edge.set_velocity(velocity)
        else:
            edge.set_weight(current_weight - self._learning_rate
                            * avg_loss_gradient)
        edge.loss_gradients = []

    def back_propagate_bias(self, neuron: Neuron):
        """Uses the bias gradients of all datapoints (for this specific neuron)
        to perform gradient descent and calculate a new bias for this neuron.

        neuron : Neuron
            The `Neuron` whose bias we are interested in updating
        """
        current_bias = neuron.get_bias()
        batch_size = len(neuron.bias_gradients)
        avg_bias_gradient = sum(neuron.bias_gradients) / batch_size
        neuron.set_bias(current_bias - self._learning_rate
                        * avg_bias_gradient)
        neuron.bias_gradients = []

    def get_edges(self) -> List[List[List[Edge]]]:
        """Getter method for edges

        Returns
        -------
        List[List[List[Edge]]]
            A list of `Edges`
        """
        return self._edges

    def get_main_layers(self) -> List[Layer]:
        """Getter method for main layers

        Returns
        -------
        List[Layer]
            A list of main `Layers`
        """
        return self._main_layers

    def get_softmax_edges(self) -> List[Edge]:
        """Getter method for softmax edges

        Returns
        -------
        typing.List
            A list of softmax `Edges`
        """
        return self._softmax_edges

    def get_neuron_counts(self) -> List[int]:
        """Getter method for neuron_counts

        Returns
        -------
        List[int]
            A list of numbers of neurons per layer
        """
        return ([self._num_features] + self._neuron_counts
                + [len(self._softmax_layer), len(self._softmax_layer)])
