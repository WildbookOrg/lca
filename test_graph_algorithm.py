import networkx as nx
import os

import graph_algorithm as ga


def check_line(name, corr, actual):
    print("%s: expected %a, actual %a, correct? %a" %
          (name, corr, actual, corr == actual))


def check_against_expected(d, gai):
    if "nodes" in d:
        check_line("nodes", d["nodes"], len(gai.G.nodes))
    if "edges" in d:
        check_line("edges", d["edges"], len(gai.G.edges))
    if "clusters" in d:
        check_line("clusters", d["clusters"], len(gai.clustering))
    if "lcas" in d:
        check_line("lcas", d["lcas"], gai.queues.num_lcas())
    if "Q" in d:
        check_line("queue Q", d["Q"], len(gai.queues.Q))
    if "S" in d:
        check_line("queue S", d["S"], len(gai.queues.S))
    if "W" in d:
        check_line("queue W", d["W"], len(gai.queues.W))
    if "score" in d:
        check_line("score", d["score"], gai.score)
    if "phase" in d:
        check_line("phase", d["phase"], gai.phase)
    if "topQ" in d and len(gai.queues.Q) == 0:
        print("Error: expected non-empty Q:", d["topQ"])
    elif "topQ" in d:
        (nodes, from_score, to_score, delta) = d["topQ"]
        a = gai.queues.top_Q()
        check_line("top of Q, nodes:", sorted(nodes), sorted(a.nodes()))
        check_line("top of Q, from_score:", from_score, a.from_score)
        if to_score is not None:
            check_line("top of Q, to_score:", to_score, a.to_score)
            check_line("top of Q, delta_score:", delta, a.delta_score())


def test_lca_in_graph_algorithm(log_fname):
    params = ga.default_params()
    aug_names = ['vamp', 'human']
    print("==============================")
    print("Testing for graph construction and then LCA operations")
    initial_edges = [('a', 'b', 3, 'vamp'),
                     ('a', 'c', 2, 'vamp'),
                     ('a', 'd', -1, 'vamp'),
                     ('b', 'd', 4, 'vamp'),
                     ('b', 'f', -2, 'vamp'),
                     ('d', 'e', 1, 'vamp')]
    initial_clustering = [('a', 'b')]
    aug_request_cb = aug_result_cb = None
    gai = ga.graph_algorithm(initial_edges, initial_clustering,
                             aug_names, params, aug_request_cb,
                             aug_result_cb, log_fname)
    print("Checking initial construction")
    d = {"lcas": 4, "clusters": 5, "nodes": 6, "edges": 6, "score": -1,
         "Q": 0, "S": 4, "W": 0}
    check_against_expected(d, gai)

    gai.compute_lca_scores()
    print("...................................\n"
          "Checking after computing LCA scores")
    del_D = {"Q": 4, "S": 0, "W": 0,
             "topQ": (('a', 'b', 'd'), 0.0, 6.0, 6.0)}
    d.update(del_D)
    check_against_expected(d, gai)

    print("...............................\n"
          "Checking after applying top LCA")
    a = gai.queues.top_Q()
    gai.score += a.delta_score()
    gai.apply_lca(a)
    del d["topQ"]
    d['lcas'] = 3
    d.update({"lcas": 3, "clusters": 4, "score": 5.0, "Q": 0, "S": 3, "W": 0})
    check_against_expected(d, gai)


class test_generator(object):
    def __init__(self, which_graph=0):
        self.no_calls_yet = True
        self.first_edges_to_add = None
        self.first_nodes_to_remove = None
        self.initial_clustering = None
        self.aug_names = ['vamp', 'human']
        self.which_graph = which_graph
        self.corr_dict = {}
        self.max_edge_delay = 0
        self.curr_edge_delay = 0
        self.aug_requested = []

        if which_graph == 0:
            self.msg = "Basic test of initializer with empty initial clusters"
            self.initial_edges = [('a', 'b', 3, 'vamp'),
                                  ('a', 'c', 2, 'vamp'),
                                  ('a', 'd', -1, 'vamp'),
                                  ('b', 'd', 5, 'vamp'),
                                  ('c', 'd', 4, 'vamp')]
            self.initial_clustering = None
            self.corr_dict = {"lcas": 5, "clusters": 4, "nodes": 4,
                              "edges": 5, "score": -13.0}

        elif which_graph == 1:
            self.msg = "Basic test of initializer with initial clusters and" \
                "\nnodes that don't have edges, and nodes in clusters that aren't" \
                " in the graph."
            self.initial_edges = [('a', 'b', 3, 'vamp'),
                                  ('a', 'c', 2, 'vamp'),
                                  ('b', 'd', 5, 'vamp'),
                                  ('c', 'd', 4, 'vamp')]
            self.initial_clustering = [('a', 'b'), ('c', 'e')]
            self.corr_dict = {"lcas": 3, "clusters": 3, "nodes": 5,
                              "edges": 4, "score": -8.0}

        elif which_graph == 2:
            self.msg = "Simple graph with single edge, no initial clusters\n" \
                       "and remove both nodes."
            self.initial_edges = [('a', 'b', 1.0, 'vamp')]
            self.first_nodes_to_remove = ['a', 'b']
            self.initial_clustering = None
            self.corr_dict = {"lcas": 0, "clusters": 0, "nodes": 0,
                              "edges": 0, "score": 0.0}
   
        elif which_graph == 3:
            self.msg = "Simple graph with single edge, nodes combined in initial cluster\n" \
                       "and remove both nodes."
            self.initial_edges = [('a', 'b', 1.0, 'vamp')]
            self.first_nodes_to_remove = ['a', 'b']
            self.initial_clustering = [['a', 'b']]
            self.corr_dict = {"lcas": 0, "clusters": 0, "nodes": 0,
                              "edges": 0, "score": 0.0}

        elif which_graph == 4:
            self.msg = "Single edge, nodes form one cluster, remove one node"
            self.initial_edges = [('a', 'b', 1.0, 'vamp')]
            self.initial_clustering = [('a', 'b')]
            self.first_nodes_to_remove = ['a']
            self.corr_dict = {"lcas": 0, "clusters": 1, "nodes": 1,
                              "edges": 0, "score": 0.0}

        elif which_graph == 5:
            self.msg = "Split apart and disconnect three node cluster"
            self.initial_edges = [('a', 'b', 3, 'vamp'),
                                  ('a', 'c', 2, 'vamp'),
                                  ('a', 'd', -1, 'vamp'),
                                  ('b', 'd', 4, 'vamp'),
                                  ('d', 'e', -1, 'vamp')]
            self.initial_clustering = [('a', 'b', 'c')]  # 'd' and 'e' will generate
            self.first_nodes_to_remove = ['a']
            self.corr_dict = {"lcas": 2, "clusters": 4, "nodes": 4,
                              "edges": 2, "score": -3.0}

        elif which_graph == 6:
            self.msg = "Repeat above with different initial cluster." \
                "\nCauses there to be two clusters created from one"
            self.initial_edges = [('a', 'b', 3, 'vamp'),
                                  ('a', 'c', 2, 'vamp'),
                                  ('a', 'd', -1, 'vamp'),
                                  ('b', 'd', 4, 'vamp'),
                                  ('d', 'e', -1, 'vamp')]
            self.initial_clustering = [('a', 'b', 'c'),
                                       ('d', 'e')]
            self.first_nodes_to_remove = ['a']
            self.corr_dict = {"lcas": 1, "clusters": 3, "nodes": 4,
                              "edges": 2, "score": -5.0}

        elif which_graph == 7:
            self.msg = \
                "Bigger remove different node; cluster remains connected;\n" \
                "but lose an LCA candidate. Also, adding an edge for\n" \
                "a node that has been removed; the edges should be\n" \
                "rejected."
            self.initial_edges = [('a', 'b', 3, 'vamp'),
                                  ('a', 'c', 2, 'vamp'),
                                  ('a', 'd', -1, 'vamp'),
                                  ('b', 'd', 4, 'vamp'),
                                  ('b', 'f', 2, 'vamp'),
                                  ('d', 'e', -1, 'vamp'),
                                  ('f', 'g', 3, 'vamp')]
            self.initial_clustering = [('a', 'b', 'c'),
                                       ('d', 'e'),
                                       ('f', 'g')]
            self.first_nodes_to_remove = ['b']
            self.first_edges_to_add = [('b', 'g', 3.0, 'vamp')]
            self.corr_dict = {"lcas": 1, "clusters": 3, "nodes": 6,
                              "edges": 4, "score": 5.0}

        elif which_graph == 8:
            self.msg = "Add edges to change an LCA and to create a new one"
            self.initial_edges = [('a', 'b', 4, 'vamp'),
                                  ('a', 'c', -2, 'vamp')]
            self.initial_clustering = [('a', 'b'), ('c'), ('d')]
            self.first_nodes_to_remove = None
            self.first_edges_to_add = [('b', 'c', 5, 'vamp'),
                                       ('c', 'd', 2, 'vamp')]
            self.corr_dict = {"lcas": 2, "clusters": 3, "nodes": 4,
                              "edges": 4, "score": -1.0}

        elif which_graph == 9:
            self.msg = \
                "Lots of edges to add in a variety of configurations,\n" \
                "including redundant edges, edges between isolated nodes,\n" \
                "between disconnected nodes, and edges within clusters.\n" \
                "Complicated by an immediate phase shift to 'splitting'"
            self.initial_edges = [('a', 'b', 5, 'vamp'),
                                  ('a', 'c', -2, 'vamp'),
                                  ('d', 'e', 3, 'vamp')]
            self.initial_clustering = [('a', 'b', 'c'), ('d', 'e'), ('f'), ('g')]
            self.first_nodes_to_remove = []
            self.first_edges_to_add = \
                [('a', 'b', 3, 'vamp'),    # ignored
                 ('a', 'c', -5, 'human'),  # add to current edge
                 ('b', 'c', 2, 'vamp'),    # within LCA
                 ('c', 'd', -4, 'vamp'),   # new LCA
                 ('e', 'f', -2, 'vamp'),   # were isolated
                 ('f', 'g', 3, 'vamp')]    # one was isolated
            self.corr_dict = {"lcas": 2, "clusters": 4, "nodes": 7,
                              "edges": 7, "score": 6.0, "phase": "splitting"}

        elif which_graph == 10:
            self.msg = "Running through several iterations, checking phase changes"
            self.initial_edges = [('a', 'b', 5, 'vamp'),
                                  ('a', 'c', -2, 'vamp'),
                                  ('c', 'd', 3, 'vamp'),
                                  ('c', 'e', 2, 'vamp')]
            self.initial_clustering = []
            self.first_nodes_to_remove = ['e']
            self.first_edges_to_add = []
            self.aug_available = {('b', 'c', 'vamp'):  5,
                                  ('b', 'd', 'vamp'): -1,
                                  ('a', 'b', 'human'): -10,
                                  ('a', 'c', 'human'): 6,
                                  ('b', 'c', 'human'): 7,
                                  ('b', 'd', 'human'): 8,
                                  ('c', 'd', 'human'): 9}
            self.corr_dict = \
                [{"nodes": 5, "edges": 4, "clusters": 5, "lcas": 4,
                  "score": -8, "Q": 0, "S": 4, "W": 0,
                  "phase": "scoring"},   # init
                 {"nodes": 4, "edges": 3, "clusters": 3, "lcas": 2,
                  "score": 4, "Q": 1, "S": 1, "W": 0,
                  "phase": "scoring",
                  "topQ": (('c', 'd'), -3, 3, 6)},  # after 1
                 {"nodes": 4, "edges": 3, "clusters": 2, "lcas": 1,
                  "score": 10, "Q": 0, "S": 1, "W": 0,
                  "phase": "scoring"},  # after 2
                 {"nodes": 4, "edges": 3, "clusters": 2, "lcas": 2,
                  "score": 10, "Q": 0, "S": 2, "W": 0,
                  "phase": "splitting"}, # after 3
                 {"nodes": 4, "edges": 3, "clusters": 2, "lcas": 3,
                  "score": 10, "Q": 2, "S": 1, "W": 0,
                  "phase": "stability",
                  "topQ": (('c', 'd'), 3.0, -3.0, -6.0)}, # after 4
                 {"nodes": 4, "edges": 3, "clusters": 2, "lcas": 3,
                  "score": 10, "Q": 2, "S": 0, "W": 1,
                  "phase": "stability",
                  "topQ": (('c', 'd'), 3.0, -3.0, -6.0)}, # after 5
                 {"nodes": 4, "edges": 5, "clusters": 1, "lcas": 1,
                  "score": 10, "Q": 0, "S": 1, "W": 0,
                  "phase": "stability"},  # after 6
                 {"nodes": 4, "edges": 5, "clusters": 1, "lcas": 1,
                  "score": 10, "Q": 0, "S": 0, "W": 1,
                  "phase": "stability"},  # after 7                 
                 {"nodes": 4, "edges": 5, "clusters": 1, "lcas": 1,
                  "score": 19, "Q": 0, "S": 0, "W": 1,
                  "phase": "stability"},  # after 8
                 {"nodes": 4, "edges": 5, "clusters": 1, "lcas": 1,
                  "score": 26, "Q": 0, "S": 0, "W": 1,
                  "phase": "stability"},  # after 9
                 {"nodes": 4, "edges": 5, "clusters": 2, "lcas": 2,
                  "score": 30, "Q": 0, "S": 2, "W": 0,
                  "phase": "stability"},  # after 10
                 {"nodes": 4, "edges": 5, "clusters": 2, "lcas": 2,
                  "score": 30, "Q": 2, "S": 0, "W": 0,
                  "phase": "stability",
                  "topQ": (('a', 'b', 'c', 'd'), 30.0, 16.0, -14.0)}]

        elif which_graph == 11:
            self.msg = "Start from a single cluster, switch to splitting" \
                "\nand then split to find the right answer."
    
            self.initial_edges = [('a', 'b', 10, 'vamp'),
                                  ('a', 'c', -4, 'vamp'),
                                  ('b', 'c', -4, 'vamp')]
            self.initial_clustering = [('a', 'b', 'c')]
            self.first_nodes_to_remove = []
            self.first_edges_to_add = []
            self.aug_available = {}
            self.corr_dict =\
                [{"nodes": 3, "edges": 3, "clusters": 1, "lcas": 1,
                  "score": 2, "Q": 0, "S": 1, "W": 0,
                  "phase": "splitting"},  # After initialization
                 {"nodes": 3, "edges": 3, "clusters": 2, "lcas": 1,
                  "score": 18, "Q": 0, "S": 1, "W": 0,
                  "phase": "splitting"},
                 {"nodes": 3, "edges": 3, "clusters": 2, "lcas": 2,
                  "score": 18, "Q": 1, "S": 1, "W": 0,
                  "phase": "stability",
                  "topQ": (('a', 'b'), 10, -10, -20)},
                 {"nodes": 3, "edges": 3, "clusters": 2, "lcas": 2,
                  "score": 18, "Q": 2, "S": 0, "W": 0,
                  "phase": "stability",
                  "topQ": (('a', 'b', 'c'), 18, 2, -16)}]

        elif which_graph == 12:
            self.msg = "Shorter example of running to convergence"
            self.initial_edges = [('a', 'b', -2, 'vamp'),
                                  ('a', 'c', 6, 'vamp'),
                                  ('b', 'd', 3, 'vamp'),
                                  ('c', 'd', 1, 'vamp')]
            self.aug_available = {('a', 'd', 'vamp'): 3,
                                  ('b', 'c', 'vamp'): -4,
                                  ('a', 'b', 'human'): -5,
                                  ('a', 'd', 'human'): 8,
                                  ('b', 'c', 'human'): -8,
                                  ('b', 'd', 'human'): 1}
            self.initial_clustering = []
            self.first_nodes_to_remove = []
            self.first_edges_to_add = []
            self.corr_dict = {"nodes": 4, "edges": 6, "clusters": 2,
                              "lcas": 2, "score": 28,
                              "Q": 2, "S": 0, "W": 0,
                              "phase": "stability",
                              "topQ": (('a', 'b', 'c', 'd'), 28, 18, -10)}

        elif which_graph == 13:
            self.msg = "Very short example of breaking apart graph."
            self.initial_edges = [('a', 'b', -2, 'vamp')]
            self.aug_available = {('a', 'b', 'human'): -8}
            self.initial_clustering = [('a', 'b')]
            self.first_nodes_to_remove = []
            self.first_edges_to_add = []
            self.corr_dict = {"nodes": 2, "edges": 1, "clusters": 2,
                              "lcas": 1, "score": 10,
                              "Q": 1, "S": 0, "W": 0,
                              "phase": "stability",
                              "score": 10,
                              "topQ": (('a', 'b'), 10, -10, -20)}

        elif which_graph == 14:
            self.msg = "Longer example of running to convergence"
            self.initial_edges = [('a', 'b', 6, 'vamp'),
                                  ('a', 'e', 3, 'vamp'),
                                  ('a', 'f', -2, 'vamp'),
                                  ('b', 'c', -4, 'vamp'),
                                  ('b', 'e', -1, 'vamp'),
                                  ('b', 'f', 1, 'vamp'),
                                  ('c', 'd', 5, 'vamp'),
                                  ('d', 'f', -3, 'vamp'),
                                  ('f', 'g', 4, 'vamp'),
                                  ('f', 'h', 5, 'vamp'),
                                  ('g', 'h', -2, 'vamp'),
                                  ('g', 'i', -2, 'vamp'),
                                  ('g', 'j', 2, 'vamp'),
                                  ('h', 'j', -3, 'vamp'),
                                  ('i', 'j', 6, 'vamp')]
            self.aug_available = {('a', 'd', 'vamp'): -6,
                                  ('a', 'g', 'vamp'): -3,
                                  ('a', 'h', 'vamp'): -4,
                                  ('b', 'd', 'vamp'): -3,
                                  ('b', 'g', 'vamp'): -2,
                                  ('b', 'h', 'vamp'): -3,
                                  ('d', 'g', 'vamp'): -3,
                                  ('d', 'h', 'vamp'): -5,
                                  ('d', 'i', 'vamp'): -9,
                                  ('d', 'j', 'vamp'): -8,
                                  ('e', 'f', 'vamp'): -4,
                                  ('e', 'g', 'vamp'): -6,
                                  ('e', 'h', 'vamp'): -5,
                                  ('f', 'i', 'vamp'): 1,
                                  ('f', 'j', 'vamp'): 1,
                                  ('h', 'i', 'vamp'): 1,
                                  ('h', 'j', 'vamp'): 2,
                                  ('a', 'e', 'human'): -5,
                                  ('a', 'f', 'human'): -3,
                                  ('b', 'e', 'human'): -4,
                                  ('b', 'f', 'human'): -2,
                                  ('f', 'g', 'human'): 6,
                                  ('g', 'h', 'human'): 5,
                                  ('g', 'j', 'human'): 8}
            self.initial_clustering = []
            self.first_nodes_to_remove = []
            self.first_edges_to_add = []
            self.corr_dict = []

        elif which_graph == 15:
            self.msg = "Small example to check termination futility"
            self.initial_edges = [('a', 'b', 4, 'vamp'),
                                  ('a', 'c', 1, 'vamp')]
            self.aug_available = {('a', 'b', 'human'): 5,
                                  ('a', 'c', 'human'): [-3, 3, -3, 3],
                                  ('b', 'c', 'vamp'): -2,
                                  ('b', 'c', 'human'): [2, 0.1, 0.1, 0.1]}
            self.initial_clustering = []
            self.first_nodes_to_remove = []
            self.first_edges_to_add = []
            self.corr_dict = {"nodes": 3, "edges": 3, "clusters": 1,
                              "lcas": 1, "score": 5.3,
                              "Q": 0, "S": 0, "W": 0,
                              "phase": "stability"}

        #  Initialize the list of what's been 

    def aug_request_cb(self, edge_triples):
        self.aug_requested += edge_triples

    def aug_result_cb(self):
        if self.no_calls_yet:
            self.no_calls_yet = False
            if self.first_edges_to_add is not None:
                return self.first_edges_to_add

        if self.curr_edge_delay > 0:
            self.curr_edge_delay -= 1
            return

        self.curr_edge_delay = self.max_edge_delay

        #  Only return those that have not already been returned
        quads = []
        for tr in self.aug_requested:
            if tr in self.aug_available:
                wgts = self.aug_available[tr]
                if type(wgts) is list:
                    w = wgts.pop(0)
                    if len(wgts) == 0:
                        del self.aug_available[tr]
                else:
                    w = wgts
                    del self.aug_available[tr]
                quads.append((tr[0], tr[1], w, tr[2]))

        self.aug_requested.clear()
        return quads

    def remove_nodes_cb(self):
        to_return = self.first_nodes_to_remove
        self.first_nodes_to_remove = []
        return to_return


def test_add_and_remove(log_fname):
    params = ga.default_params()

    graph_tests = range(10)  # was 10

    for wg in graph_tests:
        tg = test_generator(wg)
        print("===========================")
        print("Testing graph", wg)
        print(tg.msg)
        gai = ga.graph_algorithm(tg.initial_edges, tg.initial_clustering,
                                 tg.aug_names, params, tg.aug_request_cb,
                                 tg.aug_result_cb, log_fname)

        gai.set_remove_nodes_cb(tg.remove_nodes_cb)

        add_or_remove = False
        if tg.first_nodes_to_remove is not None:
            add_or_remove = True
            gai.remove_nodes()

        if tg.first_edges_to_add is not None:
            add_or_remove = True
            gai.add_edges()

        if add_or_remove:
            gai.queues.log()
            gai.queues.info_long()

        check_against_expected(tg.corr_dict, gai)


def test_iterations_and_phase_changes(log_fname,
                                      which_graph):
    params = ga.default_params()

    print("===========================================")
    tg = test_generator(which_graph=which_graph)
    print(tg.msg)
    print("Test graph: ", which_graph)
    gai = ga.graph_algorithm(tg.initial_edges, tg.initial_clustering,
                             tg.aug_names, params, tg.aug_request_cb,
                             tg.aug_result_cb, log_fname)
    gai.set_remove_nodes_cb(tg.remove_nodes_cb)

    print("......")
    print("After initialization")
    d = tg.corr_dict.pop(0)
    check_against_expected(d, gai)

    iter_num = 0
    converged = False
    while len(tg.corr_dict) > 0 and not converged:
        print("Iteration:", iter_num+1)
        d = tg.corr_dict.pop(0)
        (should_pause, iter_num, converged) = gai.run_main_loop(iter_num=iter_num,
                                                               max_iterations=iter_num+1)
        check_against_expected(d, gai)

    print(nx.get_edge_attributes(gai.G, 'weight'))
    if converged:
        print("Converged")
    elif should_pause:
        print("Error: unexpected pause.")
    else:
        print("Done with step-by-step iterations")


def run_until_convergence(log_fname, which_graph, print_graph=False):
    params = ga.default_params()
    if print_graph:
        params['draw_iterations'] = True
        params['drawing_prefix'] = "test_graph_%d" % which_graph

    print("===========================================")
    print("Test graph: ", which_graph)
    tg = test_generator(which_graph=which_graph)
    print(tg.msg)
    gai = ga.graph_algorithm(tg.initial_edges, tg.initial_clustering,
                             tg.aug_names, params, tg.aug_request_cb,
                             tg.aug_result_cb, log_fname)
    gai.set_remove_nodes_cb(tg.remove_nodes_cb)
    should_pause, iter_num, converged = \
        gai.run_main_loop(iter_num=0, max_iterations=100)

    d = None
    if type(tg.corr_dict) is list:
        if len(tg.corr_dict) > 0:
            d = tg.corr_dict[-1]
    else:
        d = tg.corr_dict
    if d is not None:
        check_against_expected(d, gai)

    if converged:
        print("Converged")
    else:
        print("Ended or paused without convergence!")


if __name__ == "__main__":
    log_fname = './test.log'
    try:
        os.remove(log_fname)
    except:
        pass

    test_lca_in_graph_algorithm(log_fname)
    test_add_and_remove(log_fname)  # which_grap in range 0..10
    test_iterations_and_phase_changes(log_fname, which_graph=10)
    test_iterations_and_phase_changes(log_fname, which_graph=11)
    run_until_convergence(log_fname, which_graph=12)
    run_until_convergence(log_fname, which_graph=13)
    run_until_convergence(log_fname, which_graph=14, print_graph=True)
    run_until_convergence(log_fname, which_graph=15)
