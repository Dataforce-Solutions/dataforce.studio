// webworker
//for debug only
DRY_RUN = false;

importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js");

const MESSAGES = {
    LOAD_PYODIDE: "LOAD_PYODIDE",
};

async function loadFalcon() {
    if (DRY_RUN) {
        return true;
    }
    const pyodide = await loadPyodide();
    await pyodide.loadPackage("micropip");


    /////////////////////////////////////////

    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/numpy-1.26.4-cp312-cp312-pyodide_2024_0_wasm32.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/scikit_learn-1.4.2-cp312-cp312-pyodide_2024_0_wasm32.whl");
    // await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/scipy-1.12.0-cp312-cp312-pyodide_2024_0_wasm32.whl");
    // await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/openblas-0.3.26.zip");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/joblib-1.4.0-py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/threadpoolctl-3.4.0-py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/protobuf-4.24.4-cp312-cp312-pyodide_2024_0_wasm32.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pandas-2.2.0-cp312-cp312-pyodide_2024_0_wasm32.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/python_dateutil-2.9.0.post0-py2.py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/six-1.16.0-py2.py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pytz-2024.1-py2.py3-none-any.whl");
    await pyodide.loadPackage("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/typing_extensions-4.11.0-py3-none-any.whl");
    await pyodide.loadPackage("/skl2onnx-1.17.0-py2.py3-none-any.whl");
    await pyodide.loadPackage("/imbalanced_learn-0.12.3-py3-none-any.whl");
    await pyodide.loadPackage("/onnxconverter_common-1.14.0-py2.py3-none-any.whl");

    //////////////////////////////////////////

    const micropip = pyodide.pyimport("micropip");


    await pyodide.loadPackage("/falcon_ml-0.8.0-py3-none-any.whl");

    await micropip.install(
        "/onnx-1.16.2-cp312-cp312-pyodide_2024_0_wasm32.whl"
    );

    await pyodide.loadPackage("/falcon_wrapper-0.1.0-py3-none-any.whl");


    await micropip.install("scipy");
    await micropip.install("optuna==4.0.0");

    self.pyodide = pyodide;
    return true;
}

self.pyodideReadyPromise = loadFalcon();


async function pingPython() {
    const fjs = self.pyodide.pyimport("falcon_wrapper");
    const res = await fjs.ping();
}

async function tabularTrain(task, data, target, groups) {
    const fjs = self.pyodide.pyimport("falcon_wrapper");
    // TODO: groups
    const model = (await fjs.tabular_train(task, data, target)).toJs();
    return JSON.parse(JSON.stringify(model));
}

async function tabularPredict(model_id, data) {
    const fjs = self.pyodide.pyimport("falcon_wrapper");
    const result = (await fjs.tabular_predict(model_id, data)).toJs();
    return JSON.parse(JSON.stringify(result));
}

async function tabularDeallocate(model_id) {
    const fjs = self.pyodide.pyimport("falcon_wrapper");
    const result = await fjs.tabular_deallocate(model_id).toJs();
    return JSON.parse(JSON.stringify(result));
}


self.onmessage = async (event) => {
    const m = event.data;
    const pyodideReady = await self.pyodideReadyPromise;
    switch (m.message) {
        case MESSAGES.LOAD_PYODIDE:
            if (pyodideReady) {
                self.postMessage({ message: m.message, id: m.id, payload: true });
            }
            // если pyodide не загрузился, надо как-то коммуницировать это обратно в main thread
            break;
        case "tabular_train":
            const tabularResult = await tabularTrain(m.payload.task, m.payload.data, m.payload.target, m.payload.groups);
            self.postMessage({ message: m.message, id: m.id, payload: tabularResult });
            break;
        case "tabular_predict":
            const tabularPredictResult = await tabularPredict(m.payload.model_id, m.payload.data);
            self.postMessage({ message: m.message, id: m.id, payload: tabularPredictResult });
            break;
        case "tabular_deallocate":
            const tabularDeallocateResult = await tabularDeallocate(m.payload.model_id);
            self.postMessage({ message: m.message, id: m.id, payload: tabularDeallocateResult });
            break;
    }
};