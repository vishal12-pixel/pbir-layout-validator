# Relaxed profile — double the Standard tolerances

Doubles the Standard thresholds for forgiving layouts:

- gap = 16 px
- overlap_tolerance = 2 px
- h_spacing_min = 16 px
- row_align_tolerance = 4 px

Format: ``<from_type> -> <to_type>: <gap>px``

card -> card: 16px
card -> actionButton: 16px
card -> tableEx: 16px
card -> shape: 16px
actionButton -> card: 16px
actionButton -> tableEx: 16px
actionButton -> actionButton: 16px
tableEx -> card: 16px
tableEx -> tableEx: 16px
tableEx -> shape: 16px
shape -> card: 16px
shape -> shape: 16px
shape -> tableEx: 16px
