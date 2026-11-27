"""Versioned local multilingual E5 inference for a verified model and tokenizer."""

from functools import lru_cache

MODEL_ID = "intfloat/multilingual-e5-base:d128750:int8"
MODEL_REVISION = "d128750597153bb5987e10b1c3493a34e5a4502a"
MODEL_FILES = {
    "encoder": ("model_qint8_avx512_vnni.onnx", 278686411,
                "2523551878658b305550d8759443822dbfda9ed9c8012ef2c354ba2c5b9de503"),
    "tokenizer": ("tokenizer.json", 17082660,
                  "62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626"),
}


@lru_cache(maxsize=2)
def encoder(model, vocabulary):
    from onnxruntime import InferenceSession, SessionOptions
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(vocabulary))
    tokenizer.enable_truncation(max_length=512)
    tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    options = SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = InferenceSession(str(model), options, providers=["CPUExecutionProvider"])
    return tokenizer, session


def embed(texts, model, vocabulary, *, query=False):
    import numpy as np

    tokenizer, session = encoder(model, vocabulary)
    prefix = "query: " if query else "passage: "
    encoded = tokenizer.encode_batch([prefix + text for text in texts])
    ids = np.asarray([item.ids for item in encoded], dtype="int64")
    masks = np.asarray([item.attention_mask for item in encoded], dtype="int64")
    inputs = {"input_ids": ids, "attention_mask": masks, "token_type_ids": np.zeros_like(ids)}
    hidden = session.run(["last_hidden_state"], {item.name: inputs[item.name] for item in session.get_inputs()})[0]
    pooled = (hidden * masks[..., None]).sum(axis=1) / masks.sum(axis=1, keepdims=True)
    vectors = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
    if vectors.shape != (len(texts), 768) or not np.isfinite(vectors).all():
        raise ValueError("GEOLLM_EMBEDDING_INVALID")
    return vectors.tolist()
