<!-- cspell:ignore jsonschema pytest ruff venv -->

# Responses API Feature Probe

Use this Python sample to observe which Microsoft Foundry Responses API features work with an
existing model deployment. It is a diagnostic proof of concept, not a Microsoft feature-parity
certification.

The sample is bring-your-own (BYO): it does not provision Azure resources, deploy a model, or run
`azd provision`, `azd deploy`, or `azd up`.

## Try it with azd

Prerequisites:

- Python 3.11 or later
- [Azure Developer CLI](https://aka.ms/install-azd)
- An existing Foundry or Azure OpenAI model deployment
- An identity with permission to invoke that deployment

Initialize the sample directly from its share branch:

```console
azd init --template https://github.com/dooriya/foundry-samples --branch rapi-feature-probe rapi-feature-probe
cd rapi-feature-probe
```

Sign in and configure the existing endpoint and deployment name:

```console
azd auth login
azd env new responses-feature-probe
azd env set FOUNDRY_PROJECT_ENDPOINT "https://<resource>.services.ai.azure.com/api/projects/<project>"
azd env set FOUNDRY_MODEL "<deployment-name>"
```

An Azure OpenAI endpoint such as `https://<resource>.openai.azure.com/openai/v1` is also
supported.

Install and run on Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install .
.\.venv\Scripts\python -m foundry_responses_feature_probe
```

Install and run on macOS or Linux:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install .
./.venv/bin/python -m foundry_responses_feature_probe
```

The run writes:

- `reports/results.json`: versioned machine-readable results
- `reports/report.md`: a readable summary

Running the probe is an explicit live-test opt-in. A full run makes ten model requests and can
incur Azure usage charges. To list scenarios or run a lower-cost subset:

```console
python -m foundry_responses_feature_probe --list-scenarios
python -m foundry_responses_feature_probe --scenario basic_response --scenario vision_input
```

## What it checks

The probe covers non-streaming and streaming responses, single and parallel function calls,
structured output, reasoning effort, prompt-cache reporting, and a deterministic 32x32 solid-black
vision input.

Capability support depends on the deployment, model, region, and configuration. An
`inconclusive` result is retained when the evidence cannot prove support or failure.

## Authentication and safety

Local authentication uses `DefaultAzureCredential`; API-key authentication is not supported.
For a Foundry project endpoint, current least-privilege guidance uses **Foundry User** at project
scope plus resource **Reader**. For an Azure OpenAI resource endpoint, use **Cognitive Services
OpenAI User**.

Reports omit prompts, responses, tool arguments, tool outputs, and token values. A final sanitizer
redacts common credential forms and sensitive URL components, but reports remain operational data
and should be reviewed before sharing. Automated tests are offline and make no network calls.

## Source tests

The source repository retains offline tests for request shapes, report schemas, credential
redaction, and the 32x32 solid-black image invariant. They are not required to run the probe and
are excluded from projects created with `azd init`.
