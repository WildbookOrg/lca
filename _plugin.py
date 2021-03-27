# -*- coding: utf-8 -*-
from wbia.control import controller_inject
from wbia.constants import CONTAINERIZED, PRODUCTION  # NOQA
from wbia import constants as const
from wbia.web.graph_server import GraphClient, GraphActor
from wbia.algo.graph.state import POSTV, NEGTV, INCMP, UNREV, UNKWN
from wbia.algo.graph.core import _rectify_decision

import numpy as np
import logging
import utool as ut

from wbia_lca import db_interface
from wbia_lca import edge_generator

import configparser
import threading
import random
import json
import sys

from wbia_lca import ga_driver
from wbia_lca import overall_driver

logger = logging.getLogger('wbia_lca')


_, register_ibs_method = controller_inject.make_ibs_register_decorator(__name__)

register_api = controller_inject.get_wbia_flask_api(__name__)
register_route = controller_inject.get_wbia_flask_route(__name__)

register_preproc_image = controller_inject.register_preprocs['image']
register_preproc_annot = controller_inject.register_preprocs['annot']


HUMAN_AUG_NAME = 'human'
HUMAN_IDENTITY = 'user:web'
HUMAN_IDENTITY_PREFIX = '%s:' % (HUMAN_IDENTITY.split(':')[0],)
ALGO_AUG_NAME = 'vamp'
ALGO_IDENTITY = 'algo:vamp'
ALGO_IDENTITY_PREFIX = '%s:' % (ALGO_IDENTITY.split(':')[0],)


@register_ibs_method
@register_api('/api/plugin/lca/sim/', methods=['GET'])
def wbia_plugin_lca_sim(ibs, ga_config, verifier_gt, request, db_result=None):
    r"""
    Create an LCA graph algorithm object and run a simulator

    Args:
        ibs (IBEISController): wbia controller object
        ga_config (str): graph algorithm config INI file
        verifier_gt (str): json file containing verification algorithm ground truth
        request (str): json file continain graph algorithm request info
        db_result (str, optional): file to write resulting json database

    Returns:
        object: changes_to_review

    CommandLine:
        python -m wbia_lca._plugin wbia_plugin_lca_sim
        python -m wbia_lca._plugin wbia_plugin_lca_sim:0
        python -m wbia_lca._plugin wbia_plugin_lca_sim:1
        python -m wbia_lca._plugin wbia_plugin_lca_sim:2

    RESTful:
        Method: GET
        URL:    /api/plugin/lca/sim/

    Doctest:
        >>> # ENABLE_DOCTEST
        >>> import wbia
        >>> import utool as ut
        >>> import random
        >>> random.seed(1)
        >>> from wbia.init import sysres
        >>> dbdir = sysres.ensure_testdb_identification_example()
        >>> ibs = wbia.opendb(dbdir=dbdir)
        >>> ga_config = 'examples/default/config.ini'
        >>> verifier_gt = 'examples/default/verifier_probs.json'
        >>> request = 'examples/default/request_example.json'
        >>> db_result = 'examples/default/result.json'
        >>> changes_to_review = ibs.wbia_plugin_lca_sim(ga_config, verifier_gt, request, db_result)
        >>> results = []
        >>> for cluster in changes_to_review:
        >>>     lines = []
        >>>     for change in cluster:
        >>>         line = []
        >>>         line.append('query nodes %s' % (sorted(change.query_nodes),))
        >>>         line.append('change_type %s' % (change.change_type,))
        >>>         line.append('old_clustering %s' % (sorted(change.old_clustering), ))
        >>>         line.append('len(new_clustering) %s' % (len(sorted(change.new_clustering)), ))
        >>>         line.append('removed_nodes %s' % (sorted(change.removed_nodes),))
        >>>         lines.append('\n'.join(line))
        >>>     results.append('\n-\n'.join(sorted(lines)))
        >>> result = '\n----\n'.join(sorted(results))
        >>> print('----\n%s\n----' % (result, ))
        ----
        query nodes ['c', 'e']
        change_type Merge
        old_clustering ['100', '101']
        len(new_clustering) 1
        removed_nodes []
        ----
        query nodes ['f']
        change_type Extension
        old_clustering ['102']
        len(new_clustering) 1
        removed_nodes []
        -
        query nodes ['g']
        change_type New
        old_clustering []
        len(new_clustering) 1
        removed_nodes []
        ----
        query nodes ['m']
        change_type Extension
        old_clustering ['103']
        len(new_clustering) 1
        removed_nodes []
        ----

    Doctest:
        >>> # ENABLE_DOCTEST
        >>> import wbia
        >>> import utool as ut
        >>> import random
        >>> random.seed(1)
        >>> from wbia.init import sysres
        >>> dbdir = sysres.ensure_testdb_identification_example()
        >>> ibs = wbia.opendb(dbdir=dbdir)
        >>> ga_config = 'examples/merge/config.ini'
        >>> verifier_gt = 'examples/merge/verifier_probs.json'
        >>> request = 'examples/merge/request_example.json'
        >>> db_result = 'examples/merge/result.json'
        >>> changes_to_review = ibs.wbia_plugin_lca_sim(ga_config, verifier_gt, request, db_result)
        >>> results = []
        >>> for cluster in changes_to_review:
        >>>     lines = []
        >>>     for change in cluster:
        >>>         line = []
        >>>         line.append('query nodes %s' % (sorted(change.query_nodes),))
        >>>         line.append('change_type %s' % (change.change_type,))
        >>>         line.append('old_clustering %s' % (sorted(change.old_clustering), ))
        >>>         line.append('len(new_clustering) %s' % (len(sorted(change.new_clustering)), ))
        >>>         line.append('removed_nodes %s' % (sorted(change.removed_nodes),))
        >>>         lines.append('\n'.join(line))
        >>>     results.append('\n-\n'.join(sorted(lines)))
        >>> result = '\n----\n'.join(sorted(results))
        >>> print('----\n%s\n----' % (result, ))
        ----
        query nodes []
        change_type Merge/Split
        old_clustering ['100', '101']
        len(new_clustering) 2
        removed_nodes []
        -
        query nodes []
        change_type Unchanged
        old_clustering ['102']
        len(new_clustering) 1
        removed_nodes []
        ----

    Doctest:
        >>> # ENABLE_DOCTEST
        >>> import wbia
        >>> import utool as ut
        >>> import random
        >>> random.seed(1)
        >>> from wbia.init import sysres
        >>> dbdir = sysres.ensure_testdb_identification_example()
        >>> ibs = wbia.opendb(dbdir=dbdir)
        >>> ga_config = 'examples/zero/config.ini'
        >>> verifier_gt = 'examples/zero/verifier_probs.json'
        >>> request = 'examples/zero/request_example.json'
        >>> db_result = 'examples/zero/result.json'
        >>> changes_to_review = ibs.wbia_plugin_lca_sim(ga_config, verifier_gt, request, db_result)
        >>> results = []
        >>> for cluster in changes_to_review:
        >>>     lines = []
        >>>     for change in cluster:
        >>>         line = []
        >>>         line.append('query nodes %s' % (sorted(change.query_nodes),))
        >>>         line.append('change_type %s' % (change.change_type,))
        >>>         line.append('old_clustering %s' % (sorted(change.old_clustering), ))
        >>>         line.append('len(new_clustering) %s' % (len(sorted(change.new_clustering)), ))
        >>>         line.append('removed_nodes %s' % (sorted(change.removed_nodes),))
        >>>         lines.append('\n'.join(line))
        >>>     results.append('\n-\n'.join(sorted(lines)))
        >>> result = '\n----\n'.join(sorted(results))
        >>> print('----\n%s\n----' % (result, ))
        ----
        query nodes ['a', 'b', 'c', 'd', 'e']
        change_type New
        old_clustering []
        len(new_clustering) 1
        removed_nodes []
        -
        query nodes ['f', 'h', 'i', 'j']
        change_type New
        old_clustering []
        len(new_clustering) 1
        removed_nodes []
        -
        query nodes ['g']
        change_type New
        old_clustering []
        len(new_clustering) 1
        removed_nodes []
        -
        query nodes ['k', 'l', 'm']
        change_type New
        old_clustering []
        len(new_clustering) 1
        removed_nodes []
        ----
    """
    # 1. Configuration
    config_ini = configparser.ConfigParser()
    config_ini.read(ga_config)

    # 2. Recent results from verification ground truth tests. Used to
    # establish the weighter.
    with open(verifier_gt, 'r') as fn:
        verifier_gt = json.loads(fn.read())

    # 3. Form the parameters dictionary and weight objects (one per
    # verification algorithm).
    ga_params, wgtrs = ga_driver.params_and_weighters(config_ini, verifier_gt)
    if len(wgtrs) > 1:
        logger.info('Not currently handling more than one weighter!!')
        sys.exit(1)
    wgtr = wgtrs[0]

    # 4. Get the request dictionary, which includes the database, the
    # actual request edges and clusters, and the edge generator edges
    # and ground truth (for simulation).
    with open(request, 'r') as fn:
        request = json.loads(fn.read())

    db = overall_driver.form_database(request)
    edge_gen = overall_driver.form_edge_generator(request, db, wgtr)
    verifier_req, human_req, cluster_req = overall_driver.extract_requests(request, db)

    # 5. Form the graph algorithm driver
    driver = ga_driver.ga_driver(
        verifier_req, human_req, cluster_req, db, edge_gen, ga_params
    )

    # 6. Run it. Changes are logged.
    ccPIC_gen = driver.run_all_ccPICs()
    changes_to_review = list(ccPIC_gen)
    print(changes_to_review)

    # 7. Commit changes. Record them in the database and the log
    # file.
    # TBD

    return changes_to_review


def is_aug_name_human(aug_name):
    return aug_name == HUMAN_AUG_NAME


def is_aug_name_algo(aug_name):
    return aug_name == ALGO_AUG_NAME


def is_identity_human(identity):
    return identity.startswith(HUMAN_IDENTITY_PREFIX)


def is_identity_algo(identity):
    return identity.startswith(ALGO_IDENTITY_PREFIX)


def convert_aug_name_to_identity(aug_name_list):
    identity_list = []
    for aug_name in aug_name_list:
        if is_aug_name_human(aug_name):
            identity = HUMAN_IDENTITY
        elif is_aug_name_algo(aug_name):
            identity = ALGO_IDENTITY
        else:
            raise ValueError()
        identity_list.append(identity)
    return identity_list


def convert_identity_to_aug_name(identity_list):
    aug_name_list = []
    for identity in identity_list:
        if is_identity_human(identity):
            aug_name = HUMAN_AUG_NAME
        elif is_identity_algo(identity):
            aug_name = ALGO_AUG_NAME
        else:
            raise ValueError()
        aug_name_list.append(aug_name)
    return aug_name_list


class db_interface_wbia(db_interface.db_interface):  # NOQA
    def __init__(self, actor):
        self.controller = actor
        self.ibs = actor.infr.ibs

        self.max_auto_reviews = 1
        self.max_human_reviews = 10
        self.max_reviews = self.max_auto_reviews + self.max_human_reviews

        edges = []
        clustering = {}
        super(db_interface_wbia, self).__init__(edges, clustering)

    # def _get_existing_weights(self, clustering):
    #     aids_set = set(self.aids)

    #     self.ibs._get_all_review()

    #     weight_rowid_list = self.ibs._get_all_edge_weight_rowids()
    #     weight_value_list = self.ibs.get_edge_weight_value(weight_rowid_list)
    #     weight_identity_list = self.ibs.get_edge_weight_identity(weight_rowid_list)

    #     edges = []
    #     for weight_rowid, weight_value, weight_identity in zip(
    #         weight_rowid_list, weight_value_list, weight_identity_list
    #     ):
    #         aid1, aid2 = self.ibs.get_edge_weight_aid_tuple(weight_rowid)
    #         if aid1 not in aids_set or aid2 not in aids_set:
    #             continue
    #         aid1_, aid2_ = str(aid1), str(aid2)

    #         if weight_identity.startswith('algo:'):
    #             aug_name = 'vamp'
    #         elif weight_identity.startswith('user:'):
    #             aug_name = 'human'
    #         else:
    #             raise ValueError()

    #         edge = (aid1_, aid2_, weight_value, aug_name)
    #         edges.append(edge)

    #     args = (
    #         len(weight_rowid_list),
    #         len(set(edges)),
    #     )
    #     logger.info('Found %d existing edge weights for %d unique edges' % args)

    #     return edges

    # def _get_existing_clustering(self):
    #     clustering_labels = list(self.infr.pos_graph.component_labels())
    #     clustering_components = list(self.infr.pos_graph.connected_components())
    #     assert len(clustering_labels) == len(clustering_components)

    #     clustering = {}
    #     for clustering_label, clustering_component in zip(clustering_labels, clustering_components):
    #         clustering_label = str(clustering_label)
    #         clustering_component = list(map(str, clustering_component))
    #         clustering[clustering_label] = clustering_component

    #     for nid in clustering:
    #         clustering[nid] = sorted(clustering[nid])

    #     args = (len(clustering),)
    #     logger.info('Retrieving clustering with %d names' % args)

    #     return clustering

    def _cleanup_edges(self, max_auto=None, max_human=None):
        if max_auto is None:
            max_auto = self.max_auto_reviews
        if max_human is None:
            max_human = self.max_human_reviews
        self.ibs.check_edge_weights(
            max_auto=max_auto,
            max_human=max_human,
        )

    def add_edges_db(self, quads):
        aid_1_list = list(map(int, ut.take_column(quads, 0)))
        aid_2_list = list(map(int, ut.take_column(quads, 1)))
        value_list = ut.take_column(quads, 2)
        aug_name_list = ut.take_column(quads, 3)
        identity_list = convert_aug_name_to_identity(aug_name_list)

        weight_rowid_list = self.ibs.add_edge_weight(
            aid_1_list, aid_2_list, value_list, identity_list
        )
        self._cleanup_edges()
        return weight_rowid_list

    # def get_weight_db(self, triple):
    #     raise RuntimeError('This should never need to be executed')

    #     n0, n1, aug_name = triple

    #     n0_, n1_ = int(n0), int(n1)
    #     edges = [(n0_, n1_)]
    #     weight_rowid_list = self.ibs.get_edge_weight_rowids_from_edges(edges)[0]
    #     weight_rowid_list = sorted(weight_rowid_list)

    #     value_list = self.ibs.get_edge_weight_value(weight_rowid_list)
    #     identity_list = self.ibs.get_edge_weight_identity(weight_rowid_list)

    #     weight = []
    #     for value, identity in zip(value_list, identity_list):
    #         if aug_name == 'human':
    #             if identity.startswith('human:'):
    #                 weight.append(value)
    #         else:
    #             weight = [value]

    #     weight = None if len(weight) == 0 else sum(weight)

    #     return weight

    def edges_from_attributes_db(self, n0, n1):
        n0_, n1_ = int(n0), int(n1)
        edges = [(n0_, n1_)]
        weight_rowid_list = self.ibs.get_edge_weight_rowids_from_edges(edges)
        weight_rowid_list = weight_rowid_list[0]
        weight_rowid_list = sorted(weight_rowid_list)

        aid_1_list = [n0] * len(weight_rowid_list)
        aid_2_list = [n1] * len(weight_rowid_list)
        value_list = self.ibs.get_edge_weight_value(weight_rowid_list)
        identity_list = self.ibs.get_edge_weight_identity(weight_rowid_list)
        aug_name_list = convert_identity_to_aug_name(identity_list)

        quads = list(zip(aid_1_list, aid_2_list, value_list, aug_name_list))

        num_vamp = aug_name_list.count(ALGO_AUG_NAME)
        num_human = aug_name_list.count(HUMAN_AUG_NAME)
        assert num_vamp <= self.max_auto_reviews
        assert num_human <= self.max_human_reviews
        assert len(quads) <= self.max_reviews

        return quads

    def commit_cluster_change_db(self, cc):
        logger.info(
            '[commit_cluster_change_db] Requested to commit cluster change: %r' % (cc,)
        )


class edge_generator_wbia(edge_generator.edge_generator):  # NOQA
    def _cleanup_edges(self):
        clean_edge_requests = []
        for edge in self.edge_requests:
            aid1_, aid2_, aug_name = edge
            aid1, aid2 = int(aid1_), int(aid2_)
            if aid1 > aid2:
                aid1, aid2 = aid2, aid1
            aid1_, aid2_ = str(aid1), str(aid2)
            clean_edge = (aid1_, aid2_, aug_name)
            clean_edge_requests.append(clean_edge)
        self.edge_requests = clean_edge_requests

    def get_edge_requests(self):
        self._cleanup_edges()
        return self.edge_requests

    def set_edge_requests(self, new_edge_requests):
        self.edge_requests = new_edge_requests
        self._cleanup_edges()
        return self.edge_requests

    def edge_request_cb_async(self):
        actor = self.controller

        requested_vamp_edges = []
        keep_edge_requests = []
        for edge in self.get_edge_requests():
            aid1_, aid2_, aug_name = edge
            if is_aug_name_algo(aug_name):
                aid1, aid2 = int(aid1_), int(aid2_)
                requested_vamp_edges.append((aid1, aid2))
            else:
                keep_edge_requests.append(edge)

        request_data = actor._candidate_edge_probs(requested_vamp_edges)
        _, requested_vamp_prob_quads, requested_vamp_quads = request_data
        self.edge_results += requested_vamp_quads
        self.set_edge_requests(keep_edge_requests)

        args = (
            len(requested_vamp_edges),
            len(requested_vamp_quads),
            len(self.edge_results),
            len(keep_edge_requests),
        )
        logger.info(
            'Received %d VAMP edge requests, added %d new results for %d total, kept %d requests in queue'
            % args
        )

    def add_feedback(
        self,
        edge,
        evidence_decision=None,
        tags=None,
        user_id=None,
        meta_decision=None,
        confidence=None,
        timestamp_c1=None,
        timestamp_c2=None,
        timestamp_s1=None,
        timestamp=None,
        verbose=None,
        priority=None,
    ):
        aid1, aid2 = edge

        if evidence_decision is None:
            evidence_decision = UNREV
        if meta_decision is None:
            meta_decision = const.META_DECISION.CODE.NULL
        decision = _rectify_decision(evidence_decision, meta_decision)

        if decision == POSTV:
            flag = True
        elif decision == NEGTV:
            flag = False
        elif decision == INCMP:
            flag = None
        else:
            # UNREV, UNKWN
            return

        aid1_, aid2_ = str(aid1), str(aid2)

        human_triples = [
            (aid1_, aid2_, flag),
        ]
        new_edge_results = self.new_edges_from_human(human_triples)
        self.edge_results += new_edge_results

        # Remove edge request for this pair now that a result has been returned
        found_edge_requests = []
        keep_edge_requests = []
        for edge in self.get_edge_requests():
            temp_aid1_, temp_aid2_, aug_name = edge
            if is_aug_name_human(aug_name):
                if temp_aid1_ == aid1_ and temp_aid2_ == aid2_:
                    found_edge_requests.append(edge)
                    continue
            keep_edge_requests.append(edge)
        args = (
            len(found_edge_requests),
            len(keep_edge_requests),
        )
        logger.info(
            'Found %d human edge requests to remove, kept %d requests in queue' % args
        )
        self.set_edge_requests(keep_edge_requests)


class LCAActor(GraphActor):
    """

    CommandLine:
        python -m wbia_lca._plugin LCAActor
        python -m wbia_lca._plugin LCAActor:0

    Doctest:
        >>> from wbia.web.graph_server import _testdata_feedback_payload
        >>> import wbia
        >>> actor = LCAActor()
        >>> # Start the process
        >>> # dbdir = wbia.sysres.db_to_dbdir('GZ_CensusAnnotation_Eval')
        >>> dbdir = wbia.sysres.db_to_dbdir('PZ_MTEST')
        >>> payload = {'action': 'start', 'dbdir': dbdir, 'aids': 'all'}
        >>> start_resp = actor.handle(payload)
        >>> print('start_resp = {!r}'.format(start_resp))
        >>> # Respond with a user decision
        >>> user_request = actor.handle({'action': 'resume'})
        >>> # Wait for a response and the LCAActor in another proc
        >>> edge, priority, edge_data = user_request[0]
        >>> user_resp_payload = _testdata_feedback_payload(edge, 'match')
        >>> content = actor.handle(user_resp_payload)
    """

    def __init__(actor, *args, **kwargs):
        actor.infr = None

        actor.warmup = True

        actor.db = None
        actor.edge_gen = None
        actor.driver = None
        actor.ga_gen = None
        actor.changes = None

        actor.resume_lock = threading.Lock()

        actor.phase = 0
        actor.loop_phase = 'init'

        # fmt: off
        actor.ga_params = {
            'aug_names': [
                ALGO_AUG_NAME,
                HUMAN_AUG_NAME,
            ],
            'prob_human_correct': 0.97,

            'min_delta_converge_multiplier': 0.95,
            'min_delta_stability_ratio': 8,
            'num_per_augmentation': 2,

            'tries_before_edge_done': 4,

            'ga_iterations_before_return': 10,
            'ga_max_num_waiting': 1000,

            'log_level': logging.INFO,
            'draw_iterations': False,
            'drawing_prefix': 'wbia_lca',
        }

        actor.config = {
            'warmup.n_peek': 50,
            'weighter_required_reviews': 50,
            'weighter_recent_reviews': 500,
            'init_nids': [],
        }
        # fmt: on

        super(LCAActor, actor).__init__(*args, **kwargs)

    def _init_infr(actor, aids, dbdir, **kwargs):
        import wbia

        assert dbdir is not None, 'must specify dbdir'
        assert actor.infr is None, 'AnnotInference already running'
        ibs = wbia.opendb(dbdir=dbdir, use_cache=False, web=False, force_serial=True)

        # Create the reference AnnotInference
        logger.info('starting via actor with ibs = %r' % (ibs,))
        actor.infr = wbia.AnnotInference(ibs=ibs, aids=aids, autoinit=True)
        actor.infr.print('started via actor')
        actor.infr.print('config = {}'.format(ut.repr3(actor.config)))

        # Configure
        for key in actor.config:
            actor.infr.params[key] = actor.config[key]

        # Pull reviews from staging
        actor.infr.print('Initializing infr tables')
        table = kwargs.get('init', 'staging')
        actor.infr.reset_feedback(table, apply=True)
        actor.infr.ensure_mst()
        actor.infr.apply_nondynamic_update()

        actor.infr.print('infr.status() = {}'.format(ut.repr4(actor.infr.status())))

        # Load VAMP models
        actor.infr.print('loading published models')
        actor.infr.load_published()

        assert actor.infr is not None

    def _get_edge_quads_ext_using_reviews(
        actor, delay_compute=False, desired_aug_name=None
    ):
        assert actor.infr is not None

        review_rowid_list = actor.infr.ibs._get_all_review_rowids()
        review_edge_list = actor.infr.ibs.get_review_aid_tuple(review_rowid_list)
        review_decision_list = actor.infr.ibs.get_review_decision(review_rowid_list)
        review_identity_list = actor.infr.ibs.get_review_identity(review_rowid_list)
        review_aug_name_list = convert_identity_to_aug_name(review_identity_list)

        if delay_compute:
            review_prob_list = [None] * len(review_rowid_list)
        else:
            review_prob_list, _, _ = actor._candidate_edge_probs(review_edge_list)

        quads_ext = []
        zipped = zip(
            review_edge_list, review_decision_list, review_prob_list, review_aug_name_list
        )
        for review_edge, review_decision, review_prob, review_aug_name in zipped:
            if desired_aug_name is not None:
                if review_aug_name != desired_aug_name:
                    continue
            aid1, aid2 = review_edge
            aid1_, aid2_ = str(aid1), str(aid2)
            review_decision_code = const.EVIDENCE_DECISION.INT_TO_CODE[review_decision]
            quad_ext = (aid1_, aid2_, review_decision_code, review_prob, review_aug_name)
            quads_ext.append(quad_ext)

        return quads_ext

    def _init_edge_weights_using_reviews(actor, desired_aug_name=None):
        assert actor.edge_gen is not None
        quads_ext = actor._get_edge_quads_ext_using_reviews(
            desired_aug_name=desired_aug_name
        )
        quads_ = [
            (aid1, aid2, weight, aug_name)
            for aid1, aid2, decision, weight, aug_name in quads_ext
        ]
        quads = actor.edge_gen.new_edges_from_verifier(quads_, db_add=False)
        return quads, quads_ext

    def _init_weighter(actor):
        logger.info('Attempting to warmup (_init_weighter)')

        assert actor.infr is not None

        quads_ext = actor._get_edge_quads_ext_using_reviews(delay_compute=True)
        logger.info('Fetched %d reviews' % (len(quads_ext),))

        verifier_gt = {
            ALGO_AUG_NAME: {
                'gt_positive_probs': [],
                'gt_negative_probs': [],
            }
        }
        for aid1, aid2, decision, weight, aug_name in quads_ext:
            edge = (
                int(aid1),
                int(aid2),
            )
            if not is_aug_name_human(aug_name):
                continue
            if decision == POSTV:
                key = 'gt_positive_probs'
            elif decision == NEGTV:
                key = 'gt_negative_probs'
            else:
                key = None
            if key is not None:
                verifier_gt[ALGO_AUG_NAME][key].append(edge)

        for algo in verifier_gt:
            for key in verifier_gt[algo]:
                edges = verifier_gt[algo][key]
                num_edges = len(edges)
                min_edges = actor.config.get('weighter_required_reviews')
                max_edges = actor.config.get('weighter_recent_reviews')
                logger.info(
                    'Found %d review edges for %s %s'
                    % (
                        num_edges,
                        algo,
                        key,
                    )
                )
                if num_edges < min_edges:
                    args = (
                        key,
                        num_edges,
                        min_edges,
                    )
                    logger.info('WARMUP failed: key %r has %d edges, needs %d' % args)
                    # return False

                thresh_edges = -1 * min(num_edges, max_edges)
                edges = edges[thresh_edges:]
                probs, _, _ = actor._candidate_edge_probs(edges)
                verifier_gt[algo][key] = probs

        wgtrs = ga_driver.generate_weighters(actor.ga_params, verifier_gt)
        actor.wgtr = wgtrs[0]

        # Update delta score thresholds
        multiplier = actor.ga_params['min_delta_converge_multiplier']
        ratio = actor.ga_params['min_delta_stability_ratio']

        human_gt_positive_weight = actor.wgtr.human_wgt(is_marked_correct=True)
        human_gt_negative_weight = actor.wgtr.human_wgt(is_marked_correct=False)

        human_gt_delta_weight = human_gt_positive_weight - human_gt_negative_weight
        convergence = -1.0 * multiplier * human_gt_delta_weight
        stability = convergence / ratio

        actor.ga_params['min_delta_score_converge'] = convergence
        actor.ga_params['min_delta_score_stability'] = stability

        logger.info(
            'Using provided   min_delta_converge_multiplier = %0.04f' % (multiplier,)
        )
        logger.info('Using provided   min_delta_stability_ratio     = %0.04f' % (ratio,))
        logger.info(
            'Using calculated min_delta_score_converge      = %0.04f' % (convergence,)
        )
        logger.info(
            'Using calculated min_delta_score_stability     = %0.04f' % (stability,)
        )

        return True

    def _init_lca(actor):
        # Initialize the weighter
        success = actor._init_weighter()
        if not success:
            return

        # Initialize the DB
        actor.db = db_interface_wbia(actor)

        # Initialize the Edge Generator
        actor.edge_gen = edge_generator_wbia(actor.db, actor.wgtr, controller=actor)

        # We have warmed up
        actor.warmup = False

    def start(actor, dbdir, aids='all', config={}, **kwargs):
        actor.config.update(config)

        # Initialize INFR
        actor._init_infr(aids, dbdir, **kwargs)

        # Initialize LCA
        actor._init_lca()

        # Initialize the review iterator
        actor._gen = actor.main_gen()

        status = 'warmup' if actor.warmup else 'initialized'
        return status

    def _candidate_edge_probs(actor, candidate_edges):
        if len(candidate_edges) == 0:
            return [], [], []

        task_probs = actor.infr._make_task_probs(candidate_edges)
        match_probs = list(task_probs['match_state']['match'])
        nomatch_probs = list(task_probs['match_state']['nomatch'])

        candidate_probs = []
        for match_prob, nomatch_prob in zip(match_probs, nomatch_probs):
            prob_ = 0.5 + (match_prob - nomatch_prob) / 2
            candidate_probs.append(prob_)

        num_probs = len(candidate_probs)
        min_probs = None if num_probs == 0 else '%0.04f' % (min(candidate_probs),)
        max_probs = None if num_probs == 0 else '%0.04f' % (max(candidate_probs),)
        mean_probs = None if num_probs == 0 else '%0.04f' % (np.mean(candidate_probs),)
        std_probs = None if num_probs == 0 else '%0.04f' % (np.std(candidate_probs),)

        args = (num_probs, min_probs, max_probs, mean_probs, std_probs)
        logger.info(
            'VAMP probabilities on %d edges (range: %s - %s, mean: %s +/- %s)' % args
        )

        if actor.edge_gen is None:
            candidate_prob_quads = None
            candidate_quads = None
        else:
            candidate_prob_quads = [
                (str(aid1), str(aid2), prob, ALGO_AUG_NAME)
                for (aid1, aid2), prob in zip(candidate_edges, candidate_probs)
            ]
            candidate_quads = actor.edge_gen.new_edges_from_verifier(
                candidate_prob_quads, db_add=False
            )

        return candidate_probs, candidate_prob_quads, candidate_quads

    def _refresh_data(actor, warmup=False, desired_states=None):
        if desired_states is None:
            desired_states = [POSTV, NEGTV, INCMP, UNREV, UNKWN]
            desired_states = desired_states + [desired_states]

        # Run LNBNN to find matches
        candidate_edges = []
        for desired_state in desired_states:
            if isinstance(desired_state, list):
                desired_states_ = desired_state
            else:
                desired_states_ = [desired_state]
            candidate_edges += actor.infr.find_lnbnn_candidate_edges(
                desired_states=desired_states_,
                can_match_samename=True,
            )
            candidate_edges += actor.infr.find_lnbnn_candidate_edges(
                desired_states=desired_states_,
                can_match_samename=False,
            )

        candidate_edges = list(set(candidate_edges))
        logger.info('Edges from LNBNN ranking %d' % (len(candidate_edges),))

        # Run VAMP on candidates
        candidate_probs, _, candidate_quads = actor._candidate_edge_probs(candidate_edges)

        # Requested warm-up, return this data immediately
        if warmup:
            warmup_data = candidate_edges, candidate_probs
            return warmup_data

        assert None not in [actor.infr, actor.db, actor.edge_gen]

        # Clear out all existing human edge weights, we will repopulate using reviews
        actor.db._cleanup_edges(max_human=0)

        # Initialize edge weights from reviews
        review_quads, review_quads_ext = actor._init_edge_weights_using_reviews()
        actor.db.add_edges_db(review_quads)

        # Initialize the edge weights from LNBNN
        actor.db.add_edges_db(candidate_quads)

        # Collect verifier results from LNBNN matches and VAMP scores
        weight_rowid_list = actor.infr.ibs._get_all_edge_weight_rowids()
        weight_edge_list = actor.infr.ibs.get_edge_weight_aid_tuple(weight_rowid_list)
        weight_edge_list = list(set(weight_edge_list))

        # Update all VAMP edges in database
        _, verifier_prob_quads, verifier_quads = actor._candidate_edge_probs(
            weight_edge_list
        )
        actor.db.add_edges_db(verifier_quads)

        verifier_results = verifier_prob_quads
        logger.info('Using %d VAMP edge weights' % (len(verifier_results),))

        # Collect human decisions
        human_decisions = []
        for aid1, aid2, decision, weight, aug_name in review_quads_ext:
            if not is_aug_name_human(aug_name):
                continue
            if decision == POSTV:
                flag = True
            elif decision == NEGTV:
                flag = False
            elif decision == INCMP:
                flag = None
            else:
                # UNREV, UNKWN
                continue
            human_decision = (aid1, aid2, flag)
            human_decisions.append(human_decision)
        logger.info('Using %d human decisions' % (len(human_decisions),))

        # Sanity check
        actor.db._cleanup_edges()
        weight_rowid_list = actor.infr.ibs._get_all_edge_weight_rowids()
        assert len(weight_rowid_list) == len(verifier_results) + len(human_decisions)

        # Purge database of edges
        actor.db._cleanup_edges(max_human=0, max_auto=0)
        weight_rowid_list = actor.infr.ibs._get_all_edge_weight_rowids()
        assert len(weight_rowid_list) == 0

        # Get the clusters to check
        cluster_ids_to_check = actor.config.get('init_nids')

        driver_data = verifier_results, human_decisions, cluster_ids_to_check
        return driver_data

    def _make_review_tuple(actor, edge, priority=1.0):
        """ Makes tuple to be sent back to the user """
        edge_data = actor.infr.get_nonvisual_edge_data(edge, on_missing='default')
        # Extra information
        edge_data['nid_edge'] = None
        if actor.edge_gen is None:
            edge_data['queue_len'] = 0
        else:
            edge_data['queue_len'] = len(actor.edge_gen.edge_requests)
        edge_data['n_ccs'] = (-1, -1)
        return (edge, priority, edge_data)

    def main_gen(actor):
        actor.phase = 0
        actor.loop_phase = 'warmup'

        while actor.warmup:
            logger.info('WARMUP: Computing warmup data')

            # We are still in warm-up, need to ask user for reviews
            warmup_data = actor._refresh_data(warmup=True, desired_states=[UNREV])
            candidate_edges, candidate_probs = warmup_data
            candidate_probs_ = list(map(int, np.around(np.array(candidate_probs) * 10.0)))

            # Create stratified buckets based on probabilities
            candidate_buckets = {}
            for candidate_edge, candidate_prob_ in zip(candidate_edges, candidate_probs_):
                if candidate_prob_ not in candidate_buckets:
                    candidate_buckets[candidate_prob_] = []
                candidate_buckets[candidate_prob_].append(candidate_edge)
            buckets = list(candidate_buckets.keys())
            logger.info('WARMUP: Creating stratified buckets: %r' % (buckets,))

            num = actor.config.get('warmup.n_peek')
            user_request = []
            for index in range(num):
                bucket = random.choice(buckets)
                edges = candidate_buckets[bucket]
                edge = random.choice(edges)
                args = (
                    bucket,
                    edge,
                )
                # logger.info('WARMUP: bucket %r, edge %r' % args)
                # Yield a bunch of random edges (from stratified buckets) to the user
                user_request += [actor._make_review_tuple(edge)]
            yield user_request

            # Try to re-initialize LCA
            actor._init_lca()

        actor.phase = 1
        actor.loop_phase = 'driver'

        if actor.driver is None:
            # Get driver data
            assert not actor.warmup
            driver_data = actor._refresh_data()
            verifier_results, human_decisions, cluster_ids_to_check = driver_data

            # Initialize the Driver
            actor.driver = ga_driver.ga_driver(
                verifier_results,
                human_decisions,
                cluster_ids_to_check,
                actor.db,
                actor.edge_gen,
                actor.ga_params,
            )

        actor.phase = 2
        actor.loop_phase = 'run_all_ccPICs'

        actor.ga_gen = actor.driver.run_all_ccPICs(yield_on_paused=True)

        changes_to_review = []
        while True:
            try:
                change_to_review = next(actor.ga_gen)
            except StopIteration:
                break

            if change_to_review is None:
                requested_human_edges = []
                for edge in actor.edge_gen.get_edge_requests():
                    aid1_, aid2_, aug_name = edge
                    if is_aug_name_human(aug_name):
                        aid1, aid2 = int(aid1_), int(aid2_)
                        requested_human_edges.append((aid1, aid2))

                args = (len(requested_human_edges),)
                logger.info('Received %d human edge requests' % args)

                user_request = []
                for edge in requested_human_edges:
                    user_request += [actor._make_review_tuple(edge)]

                yield user_request
            else:
                changes_to_review.append(change_to_review)

        actor.phase = 3
        actor.loop_phase = 'commit_cluster_change'

        for changes in changes_to_review:
            for cc in changes:
                actor.db.commit_cluster_change(cc)

        actor.phase = 4

        return 'finished:main'

    def resume(actor):
        with actor.resume_lock:
            if actor._gen is None:
                return 'finished:stopped'
            try:
                user_request = next(actor._gen)
            except StopIteration:
                actor._gen = None
                user_request = 'finished:stopiteration'
            return user_request

    def feedback(actor, **feedback):
        actor.infr.add_feedback(**feedback)
        actor.infr.write_wbia_staging_feedback()
        if actor.edge_gen is not None:
            actor.edge_gen.add_feedback(**feedback)

    def add_aids(actor, aids, **kwargs):
        raise NotImplementedError()

    def remove_aids(actor, aids, **kwargs):
        raise NotImplementedError()

    def logs(actor):
        return None

    def status(actor):
        actor_status = {}
        try:
            actor_status['phase'] = actor.phase
        except Exception:
            pass
        try:
            actor_status['loop_phase'] = actor.loop_phase
        except Exception:
            pass
        try:
            actor_status['is_inconsistent'] = False
        except Exception:
            pass
        try:
            actor_status['is_converged'] = actor.phase == 4
        except Exception:
            pass
        try:
            actor_status['num_meaningful'] = 0
        except Exception:
            pass
        try:
            actor_status['num_pccs'] = (
                None if actor.edge_gen is None else len(actor.edge_gen.edge_requests)
            )
        except Exception:
            pass
        try:
            actor_status['num_inconsistent_ccs'] = 0
        except Exception:
            pass
        try:
            actor_status['cc_status'] = {
                'num_names_max': len(actor.db.clustering),
                'num_inconsistent': 0,
            }
        except Exception:
            pass

        return actor_status

    def metadata(actor):
        if actor.infr.verifiers is None:
            actor.infr.verifiers = {}
        verifier = actor.infr.verifiers.get('match_state', None)
        extr = None if verifier is None else verifier.extr
        metadata = {
            'extr': extr,
        }
        return metadata


class LCAClient(GraphClient):
    actor_cls = LCAActor


if __name__ == '__main__':
    r"""
    CommandLine:
        python -m wbia_lca._plugin
    """
    import xdoctest

    xdoctest.doctest_module(__file__)
