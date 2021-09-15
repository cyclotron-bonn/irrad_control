This file contains plots to generate:

- Beam current (with error), reconstructed beam current and beam loss (if available) versus time.
  If possible: add residuals of beam vs reconstructed current which is good indicator of how stable the beam is in time as subplot below

- Histogram of beam position with extracted individual planes (see example in examples folder).
  The beam position histogram is already in the data under '/Histogram/BeamPosition'

- Bar plot of scan number vs rad damage ( y-axis 1: NIEL [neq/cm²], y-axis 2: TID [Mrad]) with errors

- Bar plot of row number vs rad damage (see above)