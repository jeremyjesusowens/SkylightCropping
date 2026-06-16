# Test photos

Drop a small set of test images here (jpg/jpeg/png/webp/gif) and run:

```bash
python prompt_eval.py test_photos/
```

Aim for 5-8 photos covering distinct cases, since cost scales as
`images x variants`:

- a single clear subject (person, pet, etc.)
- a group/family shot (multiple subjects)
- a pure landscape with no obvious subject
- an animal with extremities that should be excluded (e.g. a bird with
  its wings spread, or a long tail)
- a subject near the edge of the frame
- a subject facing or moving in a clear direction (to test lead-room framing)

Photos placed here are gitignored — they won't be committed to the repo.
