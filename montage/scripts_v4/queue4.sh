cd /tmp/claude-0/-home-user-agent-ai-/7e254d4a-b65c-5b2b-a811-9eb4e65e89c3/scratchpad/v4
STEP=1 SAMPLES=6 python3 scripts/flythrough4.py w r/fly > r_fly.log 2>&1; echo fly $(ls r/fly | wc -l)
STEP=2 SAMPLES=10 python3 scripts/freeze4.py w r/frz > r_frz.log 2>&1; echo frz $(ls r/frz | wc -l)
STEP=2 SAMPLES=10 python3 scripts/weapon4.py w r/wpn > r_wpn.log 2>&1; echo wpn $(ls r/wpn | wc -l)
STEP=2 SAMPLES=12 python3 scripts/replica4.py w r/rep > r_rep.log 2>&1; echo rep $(ls r/rep | wc -l)
while pgrep -f minterpolate >/dev/null; do sleep 15; done
python3 scripts/export_float4.py . ; SAMPLES=8 python3 scripts/float4.py w r/flt > r_flt.log 2>&1; echo flt $(ls r/flt | wc -l)
for k in frz wpn rep; do
  mkdir -p r/${k}_odd r/${k}_60; i=1
  for f in $(ls r/$k/*.png | sort); do n=$((10#$(basename $f .png))); if [ $((n%2)) -eq 1 ]; then ln -sf $PWD/$f r/${k}_odd/$(printf %04d $i).png; i=$((i+1)); fi; done
  ffmpeg -v error -y -framerate 30 -i r/${k}_odd/%04d.png -vf "minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" -start_number 1 r/${k}_60/%04d.png
  echo "$k 60: $(ls r/${k}_60 | wc -l)"
done
echo QUEUE4_END
