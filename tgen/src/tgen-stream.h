/*
 * See LICENSE for licensing information
 */

#ifndef SRC_TGEN_STREAM_H_
#define SRC_TGEN_STREAM_H_

#include "tgen.h"

/* the various states the read side of the connection can take */
typedef enum _TGenStreamRecvState {
    TGEN_STREAM_RECV_NONE,
    TGEN_STREAM_RECV_AUTHENTICATE,
    TGEN_STREAM_RECV_HEADER,
    TGEN_STREAM_RECV_MODEL,
    TGEN_STREAM_RECV_PAYLOAD,
    TGEN_STREAM_RECV_CHECKSUM,
    TGEN_STREAM_RECV_FOOTER,
    TGEN_STREAM_RECV_SUCCESS,
    TGEN_STREAM_RECV_ERROR,
} TGenStreamRecvState;

/* the various states the write side of the connection can take */
typedef enum _TGenStreamSendState {
    TGEN_STREAM_SEND_NONE,
    TGEN_STREAM_SEND_COMMAND,
    TGEN_STREAM_SEND_RESPONSE,
    TGEN_STREAM_SEND_PAYLOAD,
    TGEN_STREAM_SEND_CHECKSUM,
    TGEN_STREAM_SEND_FOOTER,
    TGEN_STREAM_SEND_FLUSH,
    TGEN_STREAM_SEND_SUCCESS,
    TGEN_STREAM_SEND_ERROR,
} TGenStreamSendState;

/* the various error states the connection can take */
typedef enum _TGenStreamErrorType {
    TGEN_STREAM_ERR_NONE,
    TGEN_STREAM_ERR_AUTHENTICATE,
    TGEN_STREAM_ERR_HEADER,
    TGEN_STREAM_ERR_HEADER_INCOMPLETE,
    TGEN_STREAM_ERR_HEADER_VERSION,
    TGEN_STREAM_ERR_HEADER_MODELMODE,
    TGEN_STREAM_ERR_HEADER_MODELPATH,
    TGEN_STREAM_ERR_HEADER_MODELSIZE,
    TGEN_STREAM_ERR_MODEL,
    TGEN_STREAM_ERR_CHECKSUM,
    TGEN_STREAM_ERR_FOOTER,
    TGEN_STREAM_ERR_READ,
    TGEN_STREAM_ERR_WRITE,
    TGEN_STREAM_ERR_READEOF,
    TGEN_STREAM_ERR_WRITEEOF,
    TGEN_STREAM_ERR_TIMEOUT,
    TGEN_STREAM_ERR_STALLOUT,
    TGEN_STREAM_ERR_PROXY,
    TGEN_STREAM_ERR_MISC,
} TGenStreamErrorType;

typedef enum _TGenStreamHeaderFlags {
    TGEN_HEADER_FLAG_NONE = 0,
    TGEN_HEADER_FLAG_PROTOCOL = 1 << 0,
    TGEN_HEADER_FLAG_HOSTNAME = 1 << 1,
    TGEN_HEADER_FLAG_CODE = 1 << 2,
    TGEN_HEADER_FLAG_ID = 1 << 3,
    TGEN_HEADER_FLAG_SENDSIZE = 1 << 4,
    TGEN_HEADER_FLAG_RECVSIZE = 1 << 5,
    TGEN_HEADER_FLAG_MODELNAME = 1 << 6,
    TGEN_HEADER_FLAG_MODELSEED = 1 << 7,
    TGEN_HEADER_FLAG_MODELMODE = 1 << 8, /* either 'path' or 'graphml' */
    TGEN_HEADER_FLAG_MODELPATH = 1 << 9, /* only if mode is 'path' */
    TGEN_HEADER_FLAG_MODELSIZE = 1 << 10, /* only if mode is 'graphml' */
} TGenStreamHeaderFlags;

typedef struct _NotifyCallback NotifyCallback;
struct _NotifyCallback {
    TGen_notifyFunc func;
    gpointer arg;
    GDestroyNotify argRef;
    GDestroyNotify argUnref;
    TGenActionID actionID;
};

typedef struct _TGenStream TGenStream;

struct _TGenStream {
    /* info to help describe this stream object */
    gsize id; /* global unique id for all streams created by this tgen instance */
    gchar* vertexID; /* the unique vertex id from the graph */
    gchar* hostname; /* our hostname */
    GString* stringBuffer; /* a human-readable string for logging */

    /* describes the type of error if we are in an error state */
    TGenStreamErrorType error;

    /* true if we initiated the stream (i.e., the client) */
    gboolean isCommander;

    /* the configured timeout values */
    gint64 timeoutUSecs;
    gint64 stalloutUSecs;

    /* socket communication layer and buffers */
    TGenTransport* transport;

    /* describes how this stream generates packets */
    TGenMarkovModel* mmodel;
    gboolean mmodelSendPath;

    /* information about the reading side of the connection */
    struct {
        /* current read state */
        TGenStreamRecvState state;

        /* bytes configured or requested by the peer, 0 is a special case (see below) */
        gsize requestedBytes;
        /* if TRUE and requestedBytes is 0, we should not recv anything;
         * if FALSE and requestedBytes is 0, we stop when the model ends */
        gboolean requestedZero;
        /* the number of payload bytes we expect the other end should send us, computed as
         * we make our way through the Markov model state machine.
         * this is only valid if requestedBytes is 0, and requestedZero is FALSE, because
         * otherwise both ends may repeat the model different number of times in order to
         * reach the requested send amount. */
        gsize expectedBytes;
        /* the number of payload bytes we have read */
        gsize payloadBytes;
        /* the total number of bytes we have read */
        gsize totalBytes;

        /* for buffering reads before processing */
        GString* buffer;
        /* used during authentication */
        guint authIndex;
        /* checksum over payload bytes for integrity */
        GChecksum* checksum;
    } recv;

    /* information about the writing side of the connection */
    struct {
        /* current write state */
        TGenStreamSendState state;

        /* bytes configured or requested by the peer, 0 is a special case (see below) */
        gsize requestedBytes;
        /* if TRUE and requestedBytes is 0, we should not send anything;
         * if FALSE and requestedBytes is 0, we stop when the model ends */
        gboolean requestedZero;
        /* how much did we expect to send based on the Markov model state machine */
        gsize expectedBytes;
        /* the number of payload bytes we have written */
        gsize payloadBytes;
        /* the total number of bytes we have written */
        gsize totalBytes;

        /* for buffering writes to the transport */
        GString* buffer;
        /* tracks which buffer bytes were already written */
        guint offset;
        /* checksum over payload bytes for integrity */
        GChecksum* checksum;

        /* if non-zero, then our sending model told us to pause sending until
         * g_get_monotonic_time() returns a result >= this time. */
        gint64 deferBarrierMicros;
    } send;

    /* information about the other end of the connection */
    struct {
        gchar* hostname;
        GString* buffer;
        gchar* modelName;
        guint32 modelSeed;
        gsize modelSize;
    } peer;

    /* track timings for time reporting, using g_get_monotonic_time in usec granularity */
    struct {
        gint64 nowCached;
        gint64 start;
        gint64 command;
        gint64 response;
        gint64 firstPayloadByteRecv;
        gint64 lastPayloadByteRecv;
        gint64 checksumRecv;
        gint64 footerRecv;
        gint64 firstPayloadByteSend;
        gint64 lastPayloadByteSend;
        gint64 checksumSend;
        gint64 footerSend;
        gint64 lastBytesStatusReport;
        gint64 lastTimeStatusReport;
        gint64 lastTimeErrorReport;
        gint64 lastProgress;
    } time;

    /* notification and parameters for when this stream finishes */
    NotifyCallback notifyCB;

    /* memory housekeeping */
    gint refcount;
    guint magic;
};

TGenStream* tgenstream_new(const gchar* idStr, TGenStreamOptions* options,
        TGenMarkovModel* mmodel, TGenTransport* transport, NotifyCallback notifyCB);

void tgenstream_ref(TGenStream* stream);
void tgenstream_unref(TGenStream* stream);

TGenIOResponse tgenstream_onEvent(TGenStream* stream, gint descriptor, TGenEvent events);
gboolean tgenstream_onCheckTimeout(TGenStream* stream, gint descriptor);

#endif /* SRC_TGEN_STREAM_H_ */
