"""LOCAL ONLY: transcribe a class video (teacher speaks mostly Chinese, reads Japanese) with mlx-whisper.
usage: transcribe_lecture.py <video> <out.json> [lang]   -> segments with start/end/text"""
import json, sys, time
import mlx_whisper

src, out = sys.argv[1], sys.argv[2]
lang = sys.argv[3] if len(sys.argv) > 3 else "zh"
t = time.time()
r = mlx_whisper.transcribe(src, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language=lang, temperature=0.0,
                           condition_on_previous_text=False, no_speech_threshold=0.5,
                           compression_ratio_threshold=2.2, logprob_threshold=-1.0,
                           initial_prompt="以下是日文課的上課內容，老師用中文講解日文文法與閱讀題目，答案是1、2、3、4。")
segs = [{"start": round(s["start"], 1), "end": round(s["end"], 1), "text": s["text"].strip()}
        for s in r["segments"] if s["text"].strip()]
open(out, "w", encoding="utf8").write(json.dumps(segs, ensure_ascii=False, indent=0))
print(len(segs), "segments", f"{time.time()-t:.0f}s")
