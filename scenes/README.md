## Modulus Scene Swap Demo

This folder contains four single-scene LightGuide XML programs:

- `Scene1.xml`
- `Scene2.xml`
- `Scene3.xml`
- `Scene4.xml`

Use them with the SDK hot-swap controller:

`LightGuidePy-main/LightGuidePy/examples/modulus_program_swapper.py`

Example (10-second cycle, 4 scenes):

```bash
python3 LightGuidePy-main/LightGuidePy/examples/modulus_program_swapper.py \
  --base-url http://127.0.0.1:54274 \
  --cycle-seconds 10 \
  --poll-seconds 0.2 \
  --scene scenes/Scene1.xml \
  --scene scenes/Scene2.xml \
  --scene scenes/Scene3.xml \
  --scene scenes/Scene4.xml
```

Bucket mapping is:

- `t % 10 in [0, 2.5)` -> `Scene1.xml`
- `t % 10 in [2.5, 5)` -> `Scene2.xml`
- `t % 10 in [5, 7.5)` -> `Scene3.xml`
- `t % 10 in [7.5, 10)` -> `Scene4.xml`
