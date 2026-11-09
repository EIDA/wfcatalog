"""Faster implementation of _compute_sample_metrics.

This code reimplements MSEEDMetadata._compute_sample_metrics of
obspy.signal.quality_control.MSEEDMetadata.

It uses fully vectorised numpy operations which should lead to a significant 
improvement in speed and memory efficiency.

Author: 
  @ Roman Racine, 2025

"""

import obspy.signal.quality_control 
import numpy as np

class FastMSEEDMetadata(obspy.signal.quality_control.MSEEDMetadata):
    def _compute_sample_metrics(self):
        """
        Computes metrics on samples contained in the specified time window
        """
        # Make sure there is no integer division by chance.
        npts = float(self.number_of_samples)

        self.meta['sample_min'] = min([tr.data.min() for tr in self.data])
        self.meta['sample_max'] = max([tr.data.max() for tr in self.data])


        # 
        # Vectorised implementation to reduce memory consumption and optimise running time
        #
        #

        full_samples = np.concatenate([tr.data.astype(np.float64, copy=False) for tr in self.data])


        # Manually implement these as they have to work across a list of
        # arrays.
        self.meta['sample_mean'] = full_samples.mean()


#        full_samples = np.concatenate([tr.data for tr in self.data])
        self.meta['sample_median'] = np.median(full_samples)
        self.meta['sample_lower_quartile'] = np.percentile(full_samples, 25)
        self.meta['sample_upper_quartile'] = np.percentile(full_samples, 75)



        # more memory efficient implementation of the code below
        # Roman Racine 2025-09-17
        self.meta['sample_rms'] = np.sqrt(np.mean(full_samples ** 2))

        # Sample standard deviation
        self.meta['sample_stdev'] = full_samples.std(ddof=0)


        # Percentage based availability as a function of total gap length
        # over the full trace duration
        self.meta['percent_availability'] = 100 * (
            (self.total_time - self.meta['sum_gaps']) /
            self.total_time)






