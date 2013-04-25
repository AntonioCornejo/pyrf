
def read_data_and_reflevel(dut, points=1024):
    """
    Wait for and capture a data packet and a reference level packet.
    :returns: (data_pkt, reflevel_pkt)
    """
    # capture 1 packet
    dut.capture(points, 1)

    reference_pkt = None
    # read until I get 1 data packet
    while not dut.eof():
        pkt = dut.read()

        if pkt.is_data_packet():
            break

        if 'reflevel' in pkt.fields:
            reference_pkt = pkt

    return pkt, reference_pkt

def read_data_and_reflevel_sweep(dut, startFreq, stopFreq, step):
    """
    Wait for and capture all data and reference levels packets, for
	sweep mode. Detect packets associated with start and stop
	frequencies, and return boolean variables when those events occur.
	That is necessary to aggregate data for the complete sweep span.

    :startFreq:  Lowest frequency of sweep span.
    :stopFreq:   Highest frequency of sweep span.
	:step:       Step bandwidth

    :returns: (data_pkt, reflevel_pkt, start, stop, rem, stid)
    """
    reference_pkt = None
    start = False
    stop = False
    stid = False
    rem = 0

    # read until I get 1 data packet
    while not dut.eof():
        pkt = dut.read()

        if pkt.is_data_packet():
            break

        if pkt.is_context_packet():
            if 'startid' in pkt.fields:
                stid = True
            if 'rffreq' in pkt.fields:
                cf = pkt.fields['rffreq']

                if cf == startFreq:
                    start = True
                if ((cf + step*1e6 > stopFreq) or (cf == stopFreq)):
                    stop = True
                    rem = stopFreq - cf

            if 'reflevel' in pkt.fields:
                reference_pkt = pkt

    return pkt, reference_pkt, start, stop, rem, stid

	
def socketread(socket, count, flags = None):
    """
    Retry socket read until count data received,
    like reading from a file.
    """
    if not flags:
        flags = 0
    data = socket.recv(count, flags)
    datalen = len(data)

    if datalen == 0:
        return False

    while datalen < count:
        data = data + socket.recv(count - datalen)
        datalen = len(data)

    return data
