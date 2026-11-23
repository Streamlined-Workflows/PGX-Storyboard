"""SWIFT Director's shared audio architecture: one asset system and one timeline for every audio feature.

Audio Lab, Narrator Studio, Podcast Studio, Sound Effects Studio and the storyboard all read and write the
same two things, defined in schemas.py:

  * an audio asset: one piece of sound, with where it came from and what was done to make it
  * a timeline: tracks of clips that point at assets, with every edit stored as an instruction

Nothing in this package is connected to the running application yet (Task 03, Milestone A).
"""
