"""
This pipeline is used to compute the average AIF from the different patients
to later be used in Tofts quantification.
"""

import os

import numpy as np

from scipy.optimize import curve_fit

from protoclass.data_management import DCEModality
from protoclass.data_management import GTModality

from protoclass.extraction import ToftsQuantificationExtraction

def fit_fun(t, A1, A2, T1, T2, sigma1, sigma2, alpha, beta, s, tau, delay):
    cb_t = np.zeros(t.shape)
    for idx_t in range(cb_t.size):
        cb_t[idx_t] += ((A1 / (sigma1 * np.sqrt(2. * np.pi))) *
                        (np.exp(-((t[idx_t] - T1) ** 2) /
                                (2. * sigma1 ** 2))) +
                        (alpha * np.exp(-beta * t[idx_t]) /
                         (1 + np.exp(-s * (t[idx_t] - tau)))))
        cb_t[idx_t] += ((A2 / (sigma2 * np.sqrt(2. * np.pi))) *
                        (np.exp(-((t[idx_t] - T2) ** 2) /
                                (2. * sigma2 ** 2))) +
                        (alpha * np.exp(-beta * t[idx_t]) /
                         (1 + np.exp(-s * (t[idx_t] - tau)))))
    delay = int(delay)
    cb_t = np.roll(cb_t, delay)
    cb_t[:delay] = 0.
    return cb_t

# Define the path where all the patients are
path_patients = '/data/prostate/experiments'
# Define the path of the modality to normalize
path_dce = 'DCE_reg_bspline'
# Define the path of the ground for the prostate
path_gt = 'GT_inv/prostate'
# Define the label of the ground-truth which will be provided
label_gt = ['prostate']

# Shift corresponding to the maximum shift obtained during the normalization
shift = np.array([233.33757962, 239.33121019, 242.32802548, 243.32696391,
                  247.32271762, 296.5, 376.66851169, 443.50369004,
                  468.44218942, 476.42250923, 487.39544895, 501.36100861,
                  510.33886839, 517.32164822, 522.30934809, 533.28228782,
                  539.26752768, 539.26752768, 539.26752768, 540.26506765,
                  550.2404674, 557.22324723, 557.22324723, 556.22570726,
                  556.22570726, 555.22816728, 556.99363057, 556.99363057,
                  556.99363057, 556.99363057, 556.99363057, 556.99363057,
                  556.99363057, 556.99363057, 556.99363057, 557.992569,
                  558.99150743, 558.99150743, 557.992569, 556.99363057])

# Generate the different path to be later treated
path_patients_list_dce = []
path_patients_list_gt = []
# Create the generator
id_patient_list = (name for name in os.listdir(path_patients)
                   if os.path.isdir(os.path.join(path_patients, name)))
for id_patient in id_patient_list:
    # Append for the DCE data
    path_patients_list_dce.append(os.path.join(path_patients, id_patient,
                                               path_dce))
    # Append for the GT data - Note that we need a list of gt path
    path_patients_list_gt.append([os.path.join(path_patients, id_patient,
                                               path_gt)])

# Compute the different AIF
aif_patient = []
aif_time = []
for pat_dce, pat_gt in zip(path_patients_list_dce, path_patients_list_gt):

    print 'Processing {}'.format(pat_dce)

    # Read the DCE
    dce_mod = DCEModality()
    dce_mod.read_data_from_path(pat_dce)

    for idx in range(dce_mod.data_.shape[0]):
        dce_mod.data_[idx, :] += shift[idx]

    dce_mod.update_histogram()

    # Store the time
    aif_time.append(dce_mod.time_info_)
    aif_patient.append(ToftsQuantificationExtraction.compute_aif(dce_mod,
                       estimator='median'))

# Get the median time to resample later
aif_time = np.array(aif_time)
aif_time_median = np.median(aif_time, axis=0)

# Resample each aif
for idx_aif in range(len(aif_patient)):
    aif_patient[idx_aif] = np.interp(aif_time_median, aif_time[idx_aif],
                                     aif_patient[idx_aif])

# Compute the average aif for the population
aif_patient = np.array(aif_patient)
aif_patient_avg = np.mean(aif_patient, axis=0)

# Convert the aif signal to concentration
# Parameters needed for the conversion
flip_angle_rad = np.radians(dce_mod.metadata_['flip-angle'])
T10 = 1.6
r1 = 3.5
TR = dce_mod.metadata_['TR']

start_enh = 3

# Compute the relative enhancement post-contrast / pre-contrast
s_rel = aif_patient_avg / np.min(aif_patient_avg[:start_enh])

# Compute the numerator
A = (np.exp(-2. * TR / T10) *
     np.cos(flip_angle_rad) * (1. - s_rel) +
     np.exp(-TR / T10) *
     (s_rel * np.cos(flip_angle_rad) - 1.))
# Compute the denominator
B = (np.exp(-TR / T10) *
     (np.cos(flip_angle_rad) - s_rel) + s_rel - 1.)

cb_t = np.abs((1. / (TR * r1)) * np.log(np.abs(A / B)))

init_params = [48.54, 19.8, 10.2276, 21.9, 3.378, 7.92, 1.050, 0.0028083,
               0.63463, 28.98, start_enh]
# Force the parameters to be positive
bounds = ([0] * 11, [np.inf] * 11)

popt, _ = curve_fit(fit_fun, aif_time_median, cb_t, p0=init_params,
                    bounds=bounds)

print popt
