# Contributing to AgentRx

This project welcomes contributions and suggestions. Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## How to Contribute

1. **Fork** the repository and create your branch from `main`.
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Make your changes** — keep commits focused and well-described.
4. **Test** your changes by running the pipeline on a sample trajectory:
   ```bash
   python run.py trajectories/test_random_format.json
   ```
5. **Submit a pull request** with a clear description of the change.

## Coding Conventions

- Python 3.10+
- Follow existing code style (PEP 8)
- Add docstrings to new public functions
- Keep dependencies minimal — add new packages to `requirements.txt` only when necessary

## Reporting Issues

Use [GitHub Issues](../../issues) to report bugs or request features. Please search existing issues before creating a new one.
