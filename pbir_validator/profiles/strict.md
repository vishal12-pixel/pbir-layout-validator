# Strict profile — half the Standard tolerances
# hspacing_fix = true

Halves the Standard thresholds for tighter layout discipline:

- gap = 4 px
- overlap_tolerance = 0 px
- h_spacing_min = 4 px
- row_align_tolerance = 1 px

Format: ``<from_type> -> <to_type>: <gap>px``

card -> card: 4px
card -> actionButton: 4px
card -> tableEx: 4px
card -> shape: 4px
actionButton -> card: 4px
actionButton -> tableEx: 4px
actionButton -> actionButton: 4px
tableEx -> card: 4px
tableEx -> tableEx: 4px
tableEx -> shape: 4px
shape -> card: 4px
shape -> shape: 4px
shape -> tableEx: 4px
