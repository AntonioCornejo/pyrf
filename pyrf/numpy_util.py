import math

FFT_BASELINE = -10

def compute_fft(dut, data_pkt, reflevel_pkt):
    """
    Return an array of dBm values by computing the FFT of
    the passed data and reference level.

    :param dut: WSA device
    :type dut: pyrf.devices.thinkrf.WSA4000
    :param data_pkt: packet containing samples
    :type data_pkt: pyrf.vrt.DataPacket
    :param reflevel_pkt: packet containing 'reflevel' value
    :type reflevel_pkt: pyrf.vrt.ContextPacket

    This function uses only *dut.ADC_DYNAMIC_RANGE*,
    *data_pkt.data* and *reflevel_pkt['reflevel']*.

    :returns: numpy array of dBm values as floats
    """
    import numpy # import here so docstrings are visible even without numpy

    reference_level = reflevel_pkt.fields['reflevel']

    iq_data = data_pkt.data.numpy_array()
    i_data = numpy.array(iq_data[:,0], dtype=float) / len(iq_data)
    q_data = numpy.array(iq_data[:,1], dtype=float) / len(iq_data)
    return _compute_fft(i_data, q_data, reference_level, dut.ADC_DYNAMIC_RANGE)

def get_iq_data(data_pkt):
    """
    Separate array in packet in 2 arrays, for i and q data.
	
    :param data_pkt: packet containing samples
    :type data_pkt: pyrf.vrt.DataPacket

    :returns: arrays for i and q data
    """
    import numpy
   
    iq_data = data_pkt.data.numpy_array()
    i_data = numpy.array(iq_data[:,0], dtype=float) / len(iq_data)
    q_data = numpy.array(iq_data[:,1], dtype=float) / len(iq_data)
    return i_data, q_data

def compute_avg_fft(dut, i_data, q_data, reflevel_pkt):
    reference_level = reflevel_pkt.fields['reflevel']
   
    return _compute_fft(i_data, q_data, reference_level, dut.ADC_DYNAMIC_RANGE)

def compute_fft_noLog(data_pkt):
    import numpy # import here so docstrings are visible even without numpy

    i_data, q_data = get_iq_data(data_pkt)
    return _compute_fft_noLog(i_data, q_data)
 
def _compute_fft_noLog(i_data, q_data):
    import numpy

    i_removed_dc_offset = i_data - numpy.mean(i_data)
    q_removed_dc_offset = q_data - numpy.mean(q_data)
    calibrated_q = _calibrate_i_q(i_removed_dc_offset, q_removed_dc_offset)
    iq = i_removed_dc_offset + 1j * calibrated_q
    windowed_iq = iq * numpy.hanning(len(i_data))

    fft_result = numpy.fft.fftshift(numpy.fft.fft(windowed_iq))
    return fft_result

def compute_dBm(fft_result, reflevel_pkt, adc_dynamic_range):
    import numpy
    
    reference_level = reflevel_pkt.fields['reflevel']
    noise_level_offset = reference_level - FFT_BASELINE - adc_dynamic_range
    fft_result = 20 * numpy.log10(numpy.abs(fft_result)) + noise_level_offset
    return fft_result
    
def _compute_fft(i_data, q_data, reference_level, adc_dynamic_range):
    import numpy

    i_removed_dc_offset = i_data - numpy.mean(i_data)
    q_removed_dc_offset = q_data - numpy.mean(q_data)
    calibrated_q = _calibrate_i_q(i_removed_dc_offset, q_removed_dc_offset)
    iq = i_removed_dc_offset + 1j * calibrated_q
    windowed_iq = iq * numpy.hanning(len(i_data))

    noise_level_offset = reference_level - FFT_BASELINE - adc_dynamic_range

    fft_result = numpy.fft.fftshift(numpy.fft.fft(windowed_iq))
    fft_result = 20 * numpy.log10(numpy.abs(fft_result)) + noise_level_offset

    return fft_result


def _calibrate_i_q(i_data, q_data):
    samples = len(i_data)

    sum_of_squares_i = sum(i_data ** 2)
    sum_of_squares_q = sum(q_data ** 2)

    amplitude = math.sqrt(sum_of_squares_i * 2 / samples)
    ratio = math.sqrt(sum_of_squares_i / sum_of_squares_q)

    p = (q_data / amplitude) * ratio * (i_data / amplitude)

    sinphi = 2 * sum(p) / samples
    phi_est = -math.asin(sinphi)

    return (math.sin(phi_est) * i_data + ratio * q_data) / math.cos(phi_est)


