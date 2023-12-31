/*
 * See LICENSE for licensing information
 */

#include <string.h>
#include <arpa/inet.h>
#include <glib/gstdio.h>

#include "tgen-log.h"
#include "tgen.h"

#define MAX_EVENTS_PER_IO_LOOP 100

struct _TGenDriver {
    /* our graphml dependency graph */
    TGenGraph* actionGraph;

    /* the starting action parsed from the action graph */
    TGenActionID startActionID;
    TGenStartOptions* startOptions;
    gint64 startTimeMicros;

    /* TRUE iff a condition in any endAction event has been reached */
    gboolean clientHasEnded;
    /* the server only ends if an end time is specified */
    gboolean serverHasEnded;

    /* our I/O event manager. this holds refs to all of the streams
     * and notifies them of I/O events on the underlying transports */
    TGenIO* io;

    /* traffic statistics */
    gsize heartbeatBytesRead;
    gsize heartbeatBytesWritten;
    guint64 heartbeatStreamCreated;
    guint64 heartbeatStreamSuccess;
    guint64 heartbeatStreamError;
    guint64 heartbeatFlowCreated;
    guint64 heartbeatFlowSuccess;
    guint64 heartbeatFlowError;
    guint64 heartbeatTrafficCreated;
    guint64 heartbeatTrafficSuccess;
    guint64 heartbeatTrafficError;

    gsize totalBytesRead;
    gsize totalBytesWritten;
    guint64 totalStreamCreated;
    guint64 totalStreamSuccess;
    guint64 totalStreamError;
    guint64 totalFlowCreated;
    guint64 totalFlowSuccess;
    guint64 totalFlowError;
    guint64 totalTrafficCreated;
    guint64 totalTrafficSuccess;
    guint64 totalTrafficError;

    gint refcount;
    guint magic;
};

/* forward declaration */
static gboolean _tgendriver_onStartClientTimerExpired(TGenDriver* driver, gpointer nullData);
static gboolean _tgendriver_onPauseTimerExpired(TGenDriver* driver, gpointer actionIDPtr);
static void _tgendriver_continueNextActions(TGenDriver* driver, TGenActionID actionID);

static void _tgendriver_onNotify(TGenDriver* driver, TGenActionID actionID, TGenNotifyFlags flags) {
    TGEN_ASSERT(driver);

    if(flags & TGEN_NOTIFY_STREAM_CREATED) {
        driver->heartbeatStreamCreated++;
        driver->totalStreamCreated++;
    }

    if(flags & TGEN_NOTIFY_FLOW_CREATED) {
        driver->heartbeatFlowCreated++;
        driver->totalFlowCreated++;
    }

    if(flags & TGEN_NOTIFY_TRAFFIC_CREATED) {
        driver->heartbeatTrafficCreated++;
        driver->totalTrafficCreated++;
    }

    if(flags & TGEN_NOTIFY_STREAM_COMPLETE) {
        if(flags & TGEN_NOTIFY_STREAM_SUCCESS) {
            driver->heartbeatStreamSuccess++;
            driver->totalStreamSuccess++;
        } else {
            driver->heartbeatStreamError++;
            driver->totalStreamError++;
        }
    }

    if(flags & TGEN_NOTIFY_FLOW_COMPLETE) {
        if(flags & TGEN_NOTIFY_FLOW_SUCCESS) {
            driver->heartbeatFlowSuccess++;
            driver->totalFlowSuccess++;
        } else {
            driver->heartbeatFlowError++;
            driver->totalFlowError++;
        }
    }

    if(flags & TGEN_NOTIFY_TRAFFIC_COMPLETE) {
        if(flags & TGEN_NOTIFY_TRAFFIC_SUCCESS) {
            driver->heartbeatTrafficSuccess++;
            driver->totalTrafficSuccess++;
        } else {
            driver->heartbeatTrafficError++;
            driver->totalTrafficError++;
        }
    }

    if((flags & TGEN_NOTIFY_STREAM_COMPLETE) || (flags & TGEN_NOTIFY_FLOW_COMPLETE) ||
            (flags & TGEN_NOTIFY_TRAFFIC_COMPLETE)) {
        /* We set the action ID to negative if the action was not started as part of
         * walking the action graph (we don't use 0 because that is a valid vertex id). */
        if(actionID >= 0) {
            _tgendriver_continueNextActions(driver, actionID);
        }
    }
}

static void _tgendriver_onBytesTransferred(TGenDriver* driver, gsize bytesRead, gsize bytesWritten) {
    TGEN_ASSERT(driver);

    driver->totalBytesRead += bytesRead;
    driver->heartbeatBytesRead += bytesRead;
    driver->totalBytesWritten += bytesWritten;
    driver->heartbeatBytesWritten += bytesWritten;
}

static gboolean _tgendriver_onHeartbeat(TGenDriver* driver, gpointer nullData) {
    TGEN_ASSERT(driver);

    /* check timeouts, which may cause us to close streams and update our counters */
    tgenio_checkTimeouts(driver->io);

    GString* message = g_string_new("[driver-heartbeat]");

    g_string_append_printf(message,
            " [bytes-read=%"G_GSIZE_FORMAT",bytes-written=%"G_GSIZE_FORMAT,
            driver->heartbeatBytesRead, driver->heartbeatBytesWritten);

    if(driver->heartbeatStreamCreated > 0) {
        g_string_append_printf(message,
                ",streams-created=%"G_GUINT64_FORMAT, driver->heartbeatStreamCreated);
    }

    if(driver->heartbeatStreamSuccess > 0) {
        g_string_append_printf(message,
                ",streams-succeeded=%"G_GUINT64_FORMAT, driver->heartbeatStreamSuccess);
    }

    if(driver->heartbeatStreamError > 0) {
        g_string_append_printf(message,
                ",streams-failed=%"G_GUINT64_FORMAT, driver->heartbeatStreamError);
    }

    if(driver->heartbeatFlowCreated > 0) {
        g_string_append_printf(message,
                ",flows-created=%"G_GUINT64_FORMAT, driver->heartbeatFlowCreated);
    }

    if(driver->heartbeatFlowSuccess > 0) {
        g_string_append_printf(message,
                ",flows-succeeded=%"G_GUINT64_FORMAT, driver->heartbeatFlowSuccess);
    }

    if(driver->heartbeatFlowError > 0) {
        g_string_append_printf(message,
                ",flows-failed=%"G_GUINT64_FORMAT, driver->heartbeatFlowError);
    }

    if(driver->heartbeatTrafficCreated > 0) {
        g_string_append_printf(message,
                ",traffics-created=%"G_GUINT64_FORMAT, driver->heartbeatTrafficCreated);
    }

    if(driver->heartbeatTrafficSuccess > 0) {
        g_string_append_printf(message,
                ",traffics-succeeded=%"G_GUINT64_FORMAT, driver->heartbeatTrafficSuccess);
    }

    if(driver->heartbeatTrafficError > 0) {
        g_string_append_printf(message,
                ",traffics-failed=%"G_GUINT64_FORMAT, driver->heartbeatTrafficError);
    }

    if(driver->totalStreamCreated > 0) {
        g_string_append_printf(message,
                ",total-streams-created=%"G_GUINT64_FORMAT, driver->totalStreamCreated);
    }

    if(driver->totalStreamSuccess > 0) {
        g_string_append_printf(message,
                ",total-streams-succeeded=%"G_GUINT64_FORMAT, driver->totalStreamSuccess);
    }

    if(driver->totalStreamError > 0) {
        g_string_append_printf(message,
                ",total-streams-failed=%"G_GUINT64_FORMAT, driver->totalStreamError);
    }

    guint64 streamsPending = driver->totalStreamCreated - driver->totalStreamSuccess - driver->totalStreamError;
    if(streamsPending > 0) {
        g_string_append_printf(message,
                ",total-streams-pending=%"G_GUINT64_FORMAT, streamsPending);
    }

    if(driver->totalFlowCreated > 0) {
        g_string_append_printf(message,
                ",total-flows-created=%"G_GUINT64_FORMAT, driver->totalFlowCreated);
    }

    if(driver->totalFlowSuccess > 0) {
        g_string_append_printf(message,
                ",total-flows-succeeded=%"G_GUINT64_FORMAT, driver->totalFlowSuccess);
    }

    if(driver->totalFlowError > 0) {
        g_string_append_printf(message,
                ",total-flows-failed=%"G_GUINT64_FORMAT, driver->totalFlowError);
    }

    guint64 flowsPending = driver->totalFlowCreated - driver->totalFlowSuccess - driver->totalFlowError;
    if(flowsPending > 0) {
        g_string_append_printf(message,
                ",total-flows-pending=%"G_GUINT64_FORMAT, flowsPending);
    }

    if(driver->totalTrafficCreated > 0) {
        g_string_append_printf(message,
                ",total-traffics-created=%"G_GUINT64_FORMAT, driver->totalTrafficCreated);
    }

    if(driver->totalTrafficSuccess > 0) {
        g_string_append_printf(message,
                ",total-traffics-succeeded=%"G_GUINT64_FORMAT, driver->totalTrafficSuccess);
    }

    if(driver->totalTrafficError > 0) {
        g_string_append_printf(message,
                ",total-traffics-failed=%"G_GUINT64_FORMAT, driver->totalTrafficError);
    }

    guint64 trafficsPending = driver->totalTrafficCreated - driver->totalTrafficSuccess - driver->totalTrafficError;
    if(trafficsPending > 0) {
        g_string_append_printf(message,
                ",total-traffics-pending=%"G_GUINT64_FORMAT, trafficsPending);
    }

    g_string_append_printf(message, "]");

    //tgen_message("%s", message->str);

    g_string_free(message, TRUE);

    driver->heartbeatBytesRead = 0;
    driver->heartbeatBytesWritten = 0;
    driver->heartbeatStreamCreated = 0;
    driver->heartbeatStreamSuccess = 0;
    driver->heartbeatStreamError = 0;
    driver->heartbeatFlowCreated = 0;
    driver->heartbeatFlowSuccess = 0;
    driver->heartbeatFlowError = 0;
    driver->heartbeatTrafficCreated = 0;
    driver->heartbeatTrafficSuccess = 0;
    driver->heartbeatTrafficError = 0;

    /* even if the client ended, we keep serving requests.
     * we are still running and the heartbeat timer still owns a driver ref.
     * do not cancel the timer */
    return FALSE;
}

static void _tgendriver_initBytesCB(TGenDriver* driver, NotifyBytesCallback* bytesCB) {
    bytesCB->func = (TGenTransport_notifyBytesFunc) _tgendriver_onBytesTransferred;
    bytesCB->arg = driver;
    bytesCB->argRef = (GDestroyNotify)tgendriver_ref;
    bytesCB->argUnref = (GDestroyNotify)tgendriver_unref;
}

static void _tgendriver_initNotifyCB(TGenDriver* driver, NotifyCallback* notifyCB) {
    notifyCB->func = (TGen_notifyFunc) _tgendriver_onNotify;
    notifyCB->arg = driver;
    notifyCB->argRef = (GDestroyNotify)tgendriver_ref;
    notifyCB->argUnref = (GDestroyNotify)tgendriver_unref;
    notifyCB->actionID = (TGenActionID)-1;
}

static void _tgendriver_onNewPeer(TGenDriver* driver, gint socketD, gint64 started, gint64 created, TGenPeer* peer) {
    TGEN_ASSERT(driver);

    /* we have a new peer connecting to our listening socket */
    if(driver->serverHasEnded) {
        close(socketD);
        return;
    }

    /* set up the callback function and args for the transport */
    NotifyBytesCallback bytesCB = {0};
    _tgendriver_initBytesCB(driver, &bytesCB);

    /* this connect was initiated by the other end.
     * stream information will be sent to us later.
     * bytesCB will be used to ref++ the driver in the transport. */
    TGenTransport* transport = tgentransport_newPassive(socketD, started, created, peer, bytesCB);

    if(!transport) {
        tgen_warning("failed to initialize transport for incoming peer, skipping");
        return;
    }

    TGenStreamOptions* options = &driver->startOptions->defaultTrafficOpts.flowOpts.streamOpts;

    /* set up the callback function and args for the stream */
    NotifyCallback notifyCB = {0};
    _tgendriver_initNotifyCB(driver, &notifyCB);

    /* don't send a Markov model on passive streams. sending an action id of -1 means
     * we dont try to move forward in the action graph when the stream completes.
     * notifyCB will be used to ref++ the driver in the stream. */
    TGenStream* stream = tgenstream_new("passive-stream", options, NULL, transport, notifyCB);

    if(!stream) {
        /* the transport will unref its reference to driver */
        tgentransport_unref(transport);
        tgen_warning("failed to initialize stream for incoming peer, skipping");
        return;
    }

    /* now let the IO handler manage the stream. our stream pointer reference
     * will be held by the IO object */
    tgenio_register(driver->io, tgentransport_getDescriptor(transport),
            (TGenIO_notifyEventFunc)tgenstream_onEvent,
            (TGenIO_notifyCheckTimeoutFunc) tgenstream_onCheckTimeout,
            stream, (GDestroyNotify)tgenstream_unref);

    /* release our transport pointer reference, the stream should hold one */
    tgentransport_unref(transport);
}

static gboolean _tgendriver_startGenerator(TGenDriver* driver, TGenActionID actionID,
        TGenTrafficOptions* trafficOpts, TGenFlowOptions* flowOpts, TGenStreamOptions* streamOpts) {
    TGEN_ASSERT(driver);

    const gchar* actionIDStr = tgengraph_getActionName(driver->actionGraph, actionID);

    /* setup the callback functions */
    NotifyBytesCallback bytesCB = {0};
    _tgendriver_initBytesCB(driver, &bytesCB);
    NotifyCallback notifyCB = {0};
    _tgendriver_initNotifyCB(driver, &notifyCB);

    notifyCB.actionID = actionID;

    TGenGenerator* gen = tgengenerator_new(trafficOpts, flowOpts, streamOpts,
            actionID, actionIDStr, driver->io, bytesCB, notifyCB);

    /* the generator will unref itself when it finishes generating new flows/streams and
     * all of its previously generated flows/streams are complete. */
    if(gen) {
        tgengenerator_start(gen);
        return TRUE;
    } else {
        return FALSE;
    }
}

static void _tgendriver_initiateStream(TGenDriver* driver, TGenActionID actionID) {
    TGEN_ASSERT(driver);

    TGenStreamOptions* streamOpts = tgengraph_getStreamOptions(driver->actionGraph, actionID);

    /* NULL traffic and flow options means generate just one stream */
    if(!_tgendriver_startGenerator(driver, actionID, NULL, NULL, streamOpts)) {
        const gchar* actionIDStr = tgengraph_getActionName(driver->actionGraph, actionID);
        tgen_warning("skipping failed stream action '%s' and continuing to the next action", actionIDStr);
        _tgendriver_continueNextActions(driver, actionID);
    }
}

static void _tgendriver_initiateFlow(TGenDriver* driver, TGenActionID actionID) {
    TGEN_ASSERT(driver);

    TGenFlowOptions* flowOpts = tgengraph_getFlowOptions(driver->actionGraph, actionID);
    TGenStreamOptions* streamOpts = &flowOpts->streamOpts;

    /* NULL traffic options means generate just one flow and its streams */
    if(!_tgendriver_startGenerator(driver, actionID, NULL, flowOpts, streamOpts)) {
        const gchar* actionIDStr = tgengraph_getActionName(driver->actionGraph, actionID);
        tgen_warning("skipping failed flow action '%s' and continuing to the next action", actionIDStr);
        _tgendriver_continueNextActions(driver, actionID);
    }
}

static void _tgendriver_initiateTraffic(TGenDriver* driver, TGenActionID actionID) {
    TGEN_ASSERT(driver);

    TGenTrafficOptions* trafficOpts = tgengraph_getTrafficOptions(driver->actionGraph, actionID);
    TGenFlowOptions* flowOpts = &trafficOpts->flowOpts;
    TGenStreamOptions* streamOpts = &flowOpts->streamOpts;

    /* we will create a flow model from the traffic options and generate flows with it */
    if(!_tgendriver_startGenerator(driver, actionID, trafficOpts, flowOpts, streamOpts)) {
        const gchar* actionIDStr = tgengraph_getActionName(driver->actionGraph, actionID);
        tgen_warning("skipping failed traffic action '%s' and continuing to the next action", actionIDStr);
        _tgendriver_continueNextActions(driver, actionID);
    }
}

static gboolean _tgendriver_initiatePause(TGenDriver* driver,
        TGenActionID actionID, TGenPauseOptions* options) {
    TGEN_ASSERT(driver);
    g_assert(options);

    guint64 pauseMicros = 0;
    if(options->times.isSet) {
        guint64* timeNanos = tgenpool_getRandom(options->times.value);
        g_assert(timeNanos);
        pauseMicros = (guint64)(*timeNanos / 1000);
    }

    /* if pause time is 0, just go to the next action */
    if(pauseMicros == 0) {
        tgen_info("Skipping pause action with 0 pause time");
        return FALSE;
    }

    gpointer actionIDPtr = GINT_TO_POINTER(actionID);

    /* create a timer to handle the pause action */
    TGenTimer* pauseTimer = tgentimer_new(pauseMicros, FALSE,
            (TGenTimer_notifyExpiredFunc)_tgendriver_onPauseTimerExpired, driver, actionIDPtr,
            (GDestroyNotify)tgendriver_unref, NULL);

    if(!pauseTimer) {
        tgen_warning("failed to initialize timer for pause action, skipping");
        return FALSE;
    }

    tgen_info("set pause timer for %"G_GUINT64_FORMAT" microseconds", pauseMicros);

    /* ref++ the driver and action for the pause timer */
    tgendriver_ref(driver);

    /* let the IO module handle timer reads, stream the timer pointer reference */
    tgenio_register(driver->io, tgentimer_getDescriptor(pauseTimer),
            (TGenIO_notifyEventFunc)tgentimer_onEvent, NULL, pauseTimer,
            (GDestroyNotify)tgentimer_unref);

    return TRUE;
}

static void _tgendriver_handlePause(TGenDriver* driver, TGenActionID actionID) {
    TGEN_ASSERT(driver);

    TGenPauseOptions* options = tgengraph_getPauseOptions(driver->actionGraph, actionID);

    if(options->times.isSet) {
        /* do a normal pause based on pause time */
        gboolean success = _tgendriver_initiatePause(driver, actionID, options);
        if(!success) {
            /* we have no timer set, lets just continue now so we don't stall forever */
            _tgendriver_continueNextActions(driver, actionID);
        }
    } else {
        /* do a 'synchronizing' pause where we wait until all incoming edges visit us */
        gboolean allVisited = tgengraph_incrementPauseVisited(driver->actionGraph, actionID);
        if(allVisited) {
            _tgendriver_continueNextActions(driver, actionID);
        }
    }
}

static void _tgendriver_checkEndConditions(TGenDriver* driver, TGenActionID actionID) {
    TGEN_ASSERT(driver);

    TGenEndOptions* options = tgengraph_getEndOptions(driver->actionGraph, actionID);

    /* only enforce limits if the limits are set by the user */

    if(options->sendSize.isSet) {
        if(driver->totalBytesWritten >= ((gsize)options->sendSize.value)) {
            tgen_message("TGen will end because we sent %"G_GSIZE_FORMAT" bytes "
                    "and we met or exceeded the configured send limit of %"G_GUINT64_FORMAT" bytes",
                    driver->totalBytesWritten, options->sendSize.value);
            driver->clientHasEnded = TRUE;
            driver->serverHasEnded = TRUE;
        }
    }

    if(options->recvSize.isSet) {
        if(driver->totalBytesRead >= ((gsize)options->recvSize.value)) {
            tgen_message("TGen will end because we received %"G_GSIZE_FORMAT" bytes "
                    "and we met or exceeded the configured receive limit of %"G_GUINT64_FORMAT" bytes",
                    driver->totalBytesRead, options->recvSize.value);
            driver->clientHasEnded = TRUE;
            driver->serverHasEnded = TRUE;
        }
    }

    if(options->count.isSet) {
        guint64 numStreamsCompleted = driver->totalStreamSuccess + driver->totalStreamError;
        if(numStreamsCompleted >= options->count.value) {
            tgen_message("TGen will end because we completed %"G_GUINT64_FORMAT" streams "
                    "and we met or exceeded the configured limit of %"G_GUINT64_FORMAT" streams",
                    numStreamsCompleted, options->count.value);
            driver->clientHasEnded = TRUE;
            driver->serverHasEnded = TRUE;
        }
    }

    if(options->timeNanos.isSet) {
        gint64 nowMicros = g_get_monotonic_time();
        gint64 elapsedMicros = nowMicros - driver->startTimeMicros;
        elapsedMicros = MAX(0, elapsedMicros);
        guint64 elapsedNanos = (guint64) (((guint64) elapsedMicros) * 1000);

        if(elapsedNanos >= options->timeNanos.value) {
            tgen_message("TGen will end because %"G_GUINT64_FORMAT" nanoseconds have elapsed "
                    "and we met or exceeded the configured limit of %"G_GUINT64_FORMAT" nanoseconds",
                    elapsedNanos, options->timeNanos.value);
            driver->clientHasEnded = TRUE;
            driver->serverHasEnded = TRUE;
        } else {
            tgen_message("TGen will NOT end yet because %"G_GUINT64_FORMAT" nanoseconds have elapsed "
                    "and we did not meet or exceed the configured limit of %"G_GUINT64_FORMAT" nanoseconds",
                    elapsedNanos, options->timeNanos.value);
        }
    }

    if(!driver->clientHasEnded) {
        _tgendriver_continueNextActions(driver, actionID);
    }
}

static void _tgendriver_processAction(TGenDriver* driver, TGenActionID actionID) {
    TGEN_ASSERT(driver);

    switch(tgengraph_getActionType(driver->actionGraph, actionID)) {
        case TGEN_ACTION_START: {
            /* slide through to the next actions */
            _tgendriver_continueNextActions(driver, actionID);
            break;
        }
        case TGEN_ACTION_STREAM: {
            _tgendriver_initiateStream(driver, actionID);
            break;
        }
        case TGEN_ACTION_FLOW: {
            _tgendriver_initiateFlow(driver, actionID);
            break;
        }
        case TGEN_ACTION_TRAFFIC: {
            _tgendriver_initiateTraffic(driver, actionID);
            break;
        }
        case TGEN_ACTION_END: {
            _tgendriver_checkEndConditions(driver, actionID);
            break;
        }
        case TGEN_ACTION_PAUSE: {
            _tgendriver_handlePause(driver, actionID);
            break;
        }
        case TGEN_ACTION_NONE:
        default: {
            tgen_warning("unrecognized action type");
            break;
        }
    }
}

static void _tgendriver_continueNextActions(TGenDriver* driver, TGenActionID actionID) {
    TGEN_ASSERT(driver);

    if(driver->clientHasEnded) {
        return;
    }

    const gchar* actionIDStr = tgengraph_getActionName(driver->actionGraph, actionID);
    tgen_info("Continuing to action following action ID %i (%s)", (gint)actionID, actionIDStr);

    GQueue* nextActions = tgengraph_getNextActionIDs(driver->actionGraph, actionID);
    g_assert(nextActions);

    while(g_queue_get_length(nextActions) > 0) {
        gpointer actionIDPtr = g_queue_pop_head(nextActions);
        TGenActionID nextActionID = (TGenActionID) GPOINTER_TO_INT(actionIDPtr);
        _tgendriver_processAction(driver, nextActionID);
    }

    g_queue_free(nextActions);
}

void tgendriver_activateIO(TGenDriver* driver) {
    TGEN_ASSERT(driver);

    tgen_debug("activating tgenio loop");

    gint numEventsProcessed = MAX_EVENTS_PER_IO_LOOP;

    while(numEventsProcessed >= MAX_EVENTS_PER_IO_LOOP) {
        numEventsProcessed = tgenio_loopOnce(driver->io, MAX_EVENTS_PER_IO_LOOP);
        tgen_debug("processed %i events out of the max allowed of %i", numEventsProcessed, MAX_EVENTS_PER_IO_LOOP);
    }

    tgen_debug("tgenio loop complete");
}

static void _tgendriver_free(TGenDriver* driver) {
    TGEN_ASSERT(driver);
    g_assert(driver->refcount <= 0);

    tgen_message("Freeing TGen driver state");

    if(driver->io) {
        tgenio_unref(driver->io);
    }
    if(driver->actionGraph) {
        tgengraph_unref(driver->actionGraph);
    }

    driver->magic = 0;
    g_free(driver);
}

void tgendriver_ref(TGenDriver* driver) {
    TGEN_ASSERT(driver);
    driver->refcount++;
}

void tgendriver_unref(TGenDriver* driver) {
    TGEN_ASSERT(driver);
    if(--driver->refcount <= 0) {
        _tgendriver_free(driver);
    }
}

//static gchar* _tgendriver_makeTempFile() {
//    gchar nameBuffer[256] = {0};
//    tgenconfig_gethostname(nameBuffer, 255);
//
//    GString* templateBuffer = g_string_new("XXXXXX-shadow-tgen-");
//    g_string_append_printf(templateBuffer, "%s.xml", nameBuffer);
//
//    gchar* temporaryFilename = NULL;
//    gint openedFile = g_file_open_tmp(templateBuffer->str, &temporaryFilename, NULL);
//
//    g_string_free(templateBuffer, TRUE);
//
//    if(openedFile > 0) {
//        close(openedFile);
//        return g_strdup(temporaryFilename);
//    } else {
//        return NULL;
//    }
//}

static gboolean _tgendriver_startServerHelper(TGenDriver* driver, in_port_t serverPort) {
    TGEN_ASSERT(driver);

    /* create the server that will listen for incoming connections */
    TGenServer* server = tgenserver_new(serverPort,
            (TGenServer_notifyNewPeerFunc)_tgendriver_onNewPeer, driver,
            (GDestroyNotify)tgendriver_unref);

    if(server) {
        /* the server is holding a ref to driver */
        tgendriver_ref(driver);

        /* now let the IO handler manage the server. stream our server pointer reference
         * because it will be stored as a param in the IO object */
        gint socketD = tgenserver_getDescriptor(server);
        tgenio_register(driver->io, socketD, (TGenIO_notifyEventFunc)tgenserver_onEvent, NULL,
                server, (GDestroyNotify) tgenserver_unref);

        tgen_message("Started server on port %u using descriptor %i", ntohs(serverPort), socketD);
        return TRUE;
    } else {
        tgen_critical("Unable to start server on port %u", ntohs(serverPort));
        return FALSE;
    }
}

static gboolean _tgendriver_setStartClientTimerHelper(TGenDriver* driver) {
    TGEN_ASSERT(driver);

    /* get the delay in microseconds from now to start the client */
    guint64 delayMicros = 0;
    if(driver->startOptions->timeNanos.isSet) {
        delayMicros = (guint64)(driver->startOptions->timeNanos.value / 1000);
    }

    /* client will start in the future */
    TGenTimer* startTimer = tgentimer_new(delayMicros, FALSE,
            (TGenTimer_notifyExpiredFunc)_tgendriver_onStartClientTimerExpired, driver, NULL,
            (GDestroyNotify)tgendriver_unref, NULL);

    if(startTimer) {
        /* ref++ the driver since the timer is now holding a reference */
        tgendriver_ref(driver);

        /* let the IO module handle timer reads, stream the timer pointer reference */
        gint timerD = tgentimer_getDescriptor(startTimer);
        tgenio_register(driver->io, timerD, (TGenIO_notifyEventFunc)tgentimer_onEvent, NULL,
                startTimer, (GDestroyNotify)tgentimer_unref);

        tgen_info("set startClient timer using descriptor %i", timerD);
        return TRUE;
    } else {
        return FALSE;
    }
}

static gboolean _tgendriver_setHeartbeatTimerHelper(TGenDriver* driver) {
    TGEN_ASSERT(driver);

    guint64 heartbeatPeriodMicros = 0;
    if(driver->startOptions->heartbeatPeriodNanos.isSet) {
        if(driver->startOptions->heartbeatPeriodNanos.value == 0) {
            /* do not print a heartbeat */
            tgen_warning("The heartbeat message was disabled, so log output may be sparse.");
            return TRUE;
        } else {
            heartbeatPeriodMicros = (guint64)(driver->startOptions->heartbeatPeriodNanos.value / 1000);
        }
    } else {
        heartbeatPeriodMicros = 1000*1000; /* 1 second */
    }

    /* start the heartbeat as a persistent timer event */
    TGenTimer* heartbeatTimer = tgentimer_new(heartbeatPeriodMicros, TRUE,
            (TGenTimer_notifyExpiredFunc)_tgendriver_onHeartbeat, driver, NULL,
            (GDestroyNotify)tgendriver_unref, NULL);

    if(heartbeatTimer) {
        /* ref++ the driver since the timer is now holding a reference */
        tgendriver_ref(driver);

        /* let the IO module handle timer reads, stream the timer pointer reference */
        gint timerD = tgentimer_getDescriptor(heartbeatTimer);
        tgenio_register(driver->io, timerD, (TGenIO_notifyEventFunc)tgentimer_onEvent, NULL,
                heartbeatTimer, (GDestroyNotify)tgentimer_unref);

        tgen_info("set heartbeat timer using descriptor %i", timerD);
        return TRUE;
    } else {
        return FALSE;
    }
}

TGenDriver* tgendriver_new(TGenGraph* graph) {
    /* create the main driver object */
    TGenDriver* driver = g_new0(TGenDriver, 1);
    driver->magic = TGEN_MAGIC;
    driver->refcount = 1;

    driver->io = tgenio_new();

    tgengraph_ref(graph);
    driver->actionGraph = graph;
    driver->startActionID = tgengraph_getStartActionID(graph);
    driver->startOptions = tgengraph_getStartOptions(graph);

    /* start a  status message every second */
    if(!_tgendriver_setHeartbeatTimerHelper(driver)) {
        tgendriver_unref(driver);
        return NULL;
    }

    /* only run a server if server port is set */
    if(driver->startOptions->serverport.isSet) {
        /* start a server to listen for incoming connections */
        in_port_t serverPort = htons((in_port_t)driver->startOptions->serverport.value);
        if(!_tgendriver_startServerHelper(driver, serverPort)) {
            tgendriver_unref(driver);
            return NULL;
        }
    } else {
        driver->serverHasEnded = TRUE;
    }

    /* only run the client if we have (non-start) actions we need to process */
    if(tgengraph_hasEdges(driver->actionGraph)) {
        /* the client-side streams start as specified in the graph.
         * start our client after a timeout */
        if(!_tgendriver_setStartClientTimerHelper(driver)) {
            tgendriver_unref(driver);
            return NULL;
        }
    } else {
        driver->clientHasEnded = TRUE;
    }

    return driver;
}

gint tgendriver_getEpollDescriptor(TGenDriver* driver) {
    TGEN_ASSERT(driver);
    return tgenio_getEpollDescriptor(driver->io);
}

gboolean tgendriver_hasEnded(TGenDriver* driver) {
    TGEN_ASSERT(driver);
    return (driver->clientHasEnded && driver->serverHasEnded) ? TRUE : FALSE;
}

void tgendriver_shutdownIO(TGenDriver* driver) {
    TGEN_ASSERT(driver);
    if(driver->io) {
        tgenio_unref(driver->io);
        driver->io = NULL;
    }
}

static gboolean _tgendriver_onStartClientTimerExpired(TGenDriver* driver, gpointer nullData) {
    TGEN_ASSERT(driver);

    driver->startTimeMicros = g_get_monotonic_time();

    tgen_message("starting client using action graph '%s'",
            tgengraph_getGraphPath(driver->actionGraph));
    _tgendriver_continueNextActions(driver, driver->startActionID);

    /* timer was a one time event, so it can be canceled and freed */
    return TRUE;
}

static gboolean _tgendriver_onPauseTimerExpired(TGenDriver* driver, gpointer actionIDPtr) {
    TGEN_ASSERT(driver);

    TGenActionID actionID = GPOINTER_TO_INT(actionIDPtr);

    tgen_info("pause timer expired");

    /* continue next actions if possible */
    _tgendriver_continueNextActions(driver, actionID);
    /* timer was a one time event, so it can be canceled and freed */
    return TRUE;
}