from networkx import *
import numpy as np
import random
from typing import Tuple, List, Union, Dict
from functools import reduce
from globals import TGEN_MMODEL_DELAY_CEILING
import math

# most important: firstly the struct; secondly the 'new from path' function


class MarkovModel():

    # the graph structure underlying this model
    graph: DiGraph = None

    # the identifier of the start node at which we begin traversal
    startVertex_id: str = None

    # the identifier of the node which traversal saw last
    currVertex_id: str = None

    # seed to be used by the rng
    seed: int = None

    # random number generator used by this markov model
    rng: np.random.Generator = None

    # did we find the end state?
    # NOTE the flow model does not contain an end state, I think this is because I borrowed it from tornettools where a simulation ends after a specified amount of time so the flow model itself won't end before the simulation is killed, i.e., here it will never end and we need to introduce an end state or likewise kill the simulation
    found_end_state: bool = False

    def __init__(self, path: str, startVertex_id: str, seed: int = None) -> None:
        self.graph = read_graphml(path)
        self.startVertex_id = startVertex_id
        self.currVertex_id = startVertex_id

        # seed is an optional argument. If it is not provided, we are emulating GLib's random_int, which returns a random integer equally distributed over the range [0,2^32-1] (https://docs.gtk.org/glib/func.random_int.html).
        if seed is not None:
            self.seed = seed
        else:
            self.seed = random.randint(0, pow(2, 32)-1)

        self.rng = np.random.default_rng(self.seed)

    # map vertex index ids to observation (string)
    def vertexToObservation(self, id: str) -> str:

        # firstly grab the respective node
        node: Dict[str, Union[str, float]] = self.graph.nodes[id]

        # assert the node's type is actually 'observation'
        assert (node['type'] == 'observation')

        id: str = node['name']

        if (id == '+'):

            return "OBSERVATION_TO_SERVER"

        elif (id == '-'):

            return "OBSERVATION_TO_ORIGIN"

        else:

            self.found_end_state = True

            return "OBSERVATION_END"

    # choose a random edge incident to 'self.currVertex_id' whose type matches 'edgeType'
    def chooseEdge(self, edgeType: str) -> Union[None, Tuple[str, str]]:

        # get the outgoing edges of current node
        incident_edges: List[Tuple[str, str]
                             ] = self.graph.out_edges(self.currVertex_id)

        # now we want to know the total weight of these incident edges as well as the number of edges with the specified type

        # incident edges of a vertex is just a list of tuples of the form (startVertex, targetVertex), e.g. [('s1', 's1'), ('s1', 'o1')]
        # using the start- and targetVertex of an edge, we can get its properties from the graph like this: graph.edges['s1', 's1'] - results in {'type': 'transition', 'weight': 1.0}
        # what we want is a data structure encapsulating ALL information about an edge - its start- and targetVertex as well as its properties.
        # result will look like this:
        # [{'start': 's1', 'target': 's1', 'type': 'transition', 'weight': 1.0}, {'start': 's1', 'target': 'o1', 'type': 'emission', 'weight': 1.0, 'distribution': 'exponential', 'param_rate': 3.3333333333333334e-09}]

        incident_edges_with_properties: List[Dict[str, Union[str, float]]] = list(map(
            lambda x: {**{'start': x[0], 'target': x[1]}, **(self.graph.edges[x[0], x[1]])}, incident_edges))

        # next we want to filter out only those edges that match our specified edgeType
        matching_edges: List[Dict[str, Union[str, float]]] = [
            x for x in incident_edges_with_properties if x['type'] == edgeType]

        # compute the total weight of our matching edges
        total_weight: float = reduce(
            lambda x, y: x+y, list(map(lambda x: x['weight'], matching_edges)), 0.0)

        # get a random value in the range [0.0, total_weight)
        # in tgen, they use g_rand_double_range from GLib: https://docs.gtk.org/glib/method.Rand.double_range.html
        random_value: float = self.rng.uniform(0.0, total_weight)

        # their method of picking a random edge is selecting the edge at which 'cumulative_weight' exceeds 'random_value'
        cumulative_weight: float = 0.0
        found_edge: bool = False
        chosen_edge: Tuple[str, str] = None

        for edge in matching_edges:

            cumulative_weight += edge['weight']

            if cumulative_weight >= random_value:
                found_edge = True
                chosen_edge = (edge['start'], edge['target'])
                break

        if not found_edge:
            print(
                f"Unable to choose random outgoing edge from vertex {self.currVertex_id}, {len(matching_edges)} matched edge type {edgeType}. Total weight was {total_weight}, cumulative weight was {cumulative_weight}, random value was {random_value}.")

            return None

        # return the tuple ('startVertex', 'targetVertex') which could be used to index the edge in graph.edges (as graph.edges['startVertex', 'targetVertex])
        return chosen_edge

    def chooseTransition(self) -> Tuple[Tuple[str, str], str]:
        # chooseEdge returns a Tuple defining the respective directed edge, e.g. ('s0', 's1') represents an edge s0->s1. Here we want the edge's 'target', our next state
        return self.chooseEdge('transition'), self.chooseEdge('transition')[1]

    def chooseEmission(self) -> Tuple[Tuple[str, str], str]:
        # chooseEdge returns a Tuple defining the respective directed edge, e.g. ('s0', 's1') represents an edge s0->s1. Here we want the edge's 'target', our next state
        return self.chooseEdge('emission'), self.chooseEdge('emission')[1]

    def generateDelay(self, edgeIndex: Tuple[str, str]) -> int:
        # grab the properties of this edge
        edge_dict: Dict[str, Union[str, float]
                        ] = self.graph.edges[edgeIndex[0], edgeIndex[1]]
        # grab the distribution
        distribution: str = edge_dict['distribution']

        delay: float = 0

        # now sample given the respective parameters for distribution
        if distribution == 'exponential':

            rate: float = edge_dict['param_rate']
            # numpy expects the scale parameter for sampling from exponential, which is the inverse of the rate parameter
            delay = self.rng.exponential(1/rate)

        elif distribution == 'normal':

            # requires params location, scale
            location: float = edge_dict['param_location']
            scale: float = edge_dict['param_scale']

            delay = self.rng.normal(location, scale)

        elif distribution == 'lognormal':

            # requires params location, scale
            location: float = edge_dict['param_location']
            scale: float = edge_dict['param_scale']

            # shooooot, numpy's lognormal sampling function requires mean, sd!
            # in tgen, they just sample a value from the normal dist and take the exp of this, let's do that to
            delay = math.exp(self.rng.normal(location, scale))

        elif distribution == 'pareto':

            # requires params scale, shape
            shape: float = edge_dict['param_shape']
            scale: float = edge_dict['param_scale']

            delay = self.rng.pareto(shape)
            # oh nooo it only accepts a shape param ... what to do with the scale? need to check what tgen does. .......
            # we'll leave this as a TODO since the graphml files we intend to use do not even contain any pareto-distributed emission edges.

        elif distribution == 'uniform':

            # requires params low, high
            low: float = edge_dict['param_low']
            high: float = edge_dict['param_high']

            delay = self.rng.uniform(low, high)

        else:

            print("Unknown distribution!")
            return None

        delay_rounded = round(delay)

        if (delay_rounded < 0):
            return 0
        else:
            # in tgen, they check for a possible integer overflow before casting to int; in Python, we don't need to do this since int is unbounded
            return int(delay_rounded)

    # TODO might replace the returned str representing the
    # observation type by an enum later
    def getNextObservation(self) -> Tuple[float, str]:

        # check if we are in end state
        if self.found_end_state:
            # print("Found end state!")
            return 0, 'OBSERVATION_END'

        # print(f"About to choose transition from vertex {self.currVertex_id}")

        # choose the next state through a transition edge
        # return type: Tuple[Tuple[str, str], str]
        transitionEdgeIndex, transitionObservationVertexIndex = self.chooseTransition()

        # handle error
        if not transitionObservationVertexIndex:
            print(
                f"Failed to choose a transition edge from state {self.currVertex_id}, prematurely returning end observation!")
            return 0, 'OBSERVATION_END'

        # set model's current vertex to the chosen next one
        self.currVertex_id = transitionObservationVertexIndex

        # now choose an observation through an emission edge
        # return type: Tuple[Tuple[str, str], str]
        emissionEdgeIndex, emissionObservationVertexIndex = self.chooseEmission()

        # handle error
        if not emissionEdgeIndex:
            print(
                f"Failed to choose an emission edge from state {self.currVertex_id}, prematurely returning end observation!")
            return 0, 'OBSERVATION_END'

        # sample delay
        delay: float = self.generateDelay(emissionEdgeIndex)
        if delay > TGEN_MMODEL_DELAY_CEILING:
            delay = TGEN_MMODEL_DELAY_CEILING

        emissionObservationVertexIndex_str = self.vertexToObservation(
            emissionObservationVertexIndex)

        # print for debugging
        """
        if emissionObservationVertexIndex_str == "OBSERVATION_TO_SERVER":

            print(
                f"Markov model with seed {self.seed} found OBSERVATION_TO_SERVER with delay of {delay} microseconds")

        elif emissionObservationVertexIndex_str == "OBSERVATION_TO_ORIGIN":

            print(
                f"Markov model with seed {self.seed} found OBSERVATION_TO_ORIGIN with delay of {delay} microseconds")

        else:

            print(
                f"Markov model with seed {self.seed} found OBSERVATION_END with delay of {delay} microseconds")
        """

        return delay, emissionObservationVertexIndex_str
