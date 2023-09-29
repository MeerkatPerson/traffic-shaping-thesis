/*
 * See LICENSE for licensing information
 */

#ifndef TGEN_MARKOVMODEL_H_
#define TGEN_MARKOVMODEL_H_

#include <glib.h>
#include <igraph.h>

/* this is how many bytes we send for each packet type observation */
#define TGEN_MMODEL_PACKET_DATA_SIZE 1434
/* and packets sent within this many microseconds will be sent
 * at the same time for efficiency reasons */
#define TGEN_MMODEL_MICROS_AT_ONCE 10000

typedef enum _Observation Observation;
enum _Observation {
    OBSERVATION_TO_SERVER,
    OBSERVATION_TO_ORIGIN,
    OBSERVATION_END,
};

typedef struct _TGenMarkovModel TGenMarkovModel;

struct _TGenMarkovModel {
    gint refcount;

    /* For generating deterministic pseudo-random sequences. */
    GRand* prng;
    guint32 prngSeed;

    /* The name of the graphml file that we loaded. */
    gchar* name;
    /* The path of the graphml file, may be NULL if we initiated from a string */
    gchar* path;

    igraph_t* graph;
    igraph_integer_t startVertexIndex;
    igraph_integer_t currentStateVertexIndex;
    gboolean foundEndState;

    guint magic;
};

/* Note: a random seed can be generated from the global prng with `guint32 seed = g_random_int();` */
TGenMarkovModel* tgenmarkovmodel_newFromString(const gchar* name, guint32 seed, const GString* graphmlString);
/* Note: a name can be computed from a path using `gchar* name = g_path_get_basename(path);` */
TGenMarkovModel* tgenmarkovmodel_newFromPath(const gchar* name, guint32 seed, const gchar* graphmlFilePath);

void tgenmarkovmodel_ref(TGenMarkovModel* mmodel);
void tgenmarkovmodel_unref(TGenMarkovModel* mmodel);

Observation tgenmarkovmodel_getNextObservation(TGenMarkovModel* mmodel, guint64* delay);
gboolean tgenmarkovmodel_isInEndState(TGenMarkovModel* mmodel);
void tgenmarkovmodel_reset(TGenMarkovModel* mmodel);

guint32 tgenmarkovmodel_getSeed(TGenMarkovModel* mmodel);
const gchar* tgenmarkovmodel_getName(TGenMarkovModel* mmodel);
const gchar* tgenmarkovmodel_getPath(TGenMarkovModel* mmodel);

GString* tgenmarkovmodel_toGraphmlString(TGenMarkovModel* mmodel);

#endif /* TGEN_MARKOVMODEL_H_ */
