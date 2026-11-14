import traceback
from nlp.pipeline import SatQueryNLPPipeline

print("START", flush=True)

try:
    pipeline = SatQueryNLPPipeline()
    print("INITIALIZED", flush=True)

    result = pipeline.process_query(
        "Detect flooded areas in the image."
    )

    print("PIPELINE RESULT:", result, flush=True)

except BaseException as error:
    print("PIPELINE FAILURE:", type(error).__name__, str(error), flush=True)
    traceback.print_exc()
