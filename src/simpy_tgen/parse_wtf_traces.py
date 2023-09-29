from typing import Dict, Tuple
# use the 'OrderedDict' type to ensure that data emission events within a stream are sorted by key, where key = time
from collections import OrderedDict

from globals import MICROSECONDS_PER_SECOND


def parse_wtf_traffic(run: int, num: int) -> Dict:

    # our data dict will only contain one stream in this case because the traces are quite minimal, only containing "time, bytes (direction)" tuples
    data_dict = {'streams': dict()}

    start_time = None

    last_emission_event = None

    ind = 0

    for line in open(f"../../wtf-traces/{run}-{num}"):

        # lines have the form 1392354060.410873	-565, where the first chunk is the timestamp seconds.microseconds and the second chunk are the transferred bytes, negative if incoming, positive if outgoing (https://github.com/wtfpad/wtfpad/blob/master/src/constants.py)
        line_chunks = line.strip().split('\t')

        # 1392354060.410873, i.e., UNIX time seconds.microseconds
        time = line_chunks[0].split(".")

        time_unix_seconds = int(time[0])

        if ind == 0:

            # we'll pretend for no reason whatsoever that the seconds portion of the first line in the file is our start time and compute everything else relative to that
            start_time = time_unix_seconds

            data_dict['streams'].update(
                {0: {'time_created': start_time, 'emissions': dict(), 'delay': 0}})

        # adjust for start time
        time_adjusted_seconds = time_unix_seconds - start_time

        # grab microseconds
        time_microseconds = int(time[1])

        # compute total microseconds
        time_total = time_adjusted_seconds * MICROSECONDS_PER_SECOND + time_microseconds

        # grab number of bytes transferred & direction
        num_bytes = int(line_chunks[1])

        direction = 'TO_SERVER' if num_bytes > 0 else 'TO_ORIGIN'

        # check if this timeval is already contained in our dict
        if time_total in data_dict['streams'][0]['emissions']:

            print("Time collision, appending!")

            data_dict['streams'][0]['emissions'][time_total].append(
                {'direction': direction, 'bytes': abs(num_bytes)})

        else:

            data_dict['streams'][0]['emissions'].update(
                {time_total: [{'direction': direction, 'bytes': abs(num_bytes)}]})

        ind += 1

    # next we want to compute the respective delays in between emissions
    sorted_emission_events = OrderedDict(
        sorted(data_dict['streams'][0]['emissions'].items()))

    data_dict['streams'][0]['emissions'] = dict()

    # bootstrap 'last_emission_event' so we can compute delay in between stream creation and first emission event
    last_emission_event = 0

    # now let's also compute the delays for the emission events on this stream
    for emission_key, emission_val in sorted_emission_events.items():

        # emission_key = emission_time; now compute the delay in between this emission and the previous one respectively the creation of the stream if this is the first emission event
        delay = emission_key - last_emission_event

        # sanity check
        if delay < 0:
            print("Something went wrong, negative delay!! (Emission level)")

        # now we're making a keeeeewwwwl dict key which is a tuple of the form (time, delay) where time is the respective timestamp in microseconds adjusted for start time and the delay is the inter-emission delay so we know how long to wait in between emissions.
        # this ensures uniqueness of dict keys, if we'd use the delays as dict keys we'd likely overwrite data from time to time due to collisions
        key: Tuple[int, int] = (emission_key, delay)

        data_dict['streams'][0]['emissions'].update({
            key: emission_val})

        last_emission_event = emission_key

    return data_dict
