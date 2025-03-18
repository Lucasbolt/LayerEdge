# LayerEdge
automation script for running LayerEdge node. 

## Features

- Automates the process of running LayerEdge nodes.
- Supports private key validation and proxy management.
- Handles node activation, deactivation, and daily point claims.
- Includes error handling and retry mechanisms for robustness.
- Provides logging for better traceability.

## Prerequisites

- Python 3.8 or higher.
- Install the required dependencies listed in `requirements.txt`.

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/Lucasbolt/LayerEdge.git
    cd LayerEdge
    ```

2. Create private key and proxies file:
    ```bash
    touch privatekeys.txt
    ```

2. Create and activate a virtual environment:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1. Add your private keys to `privatekeys.txt` (one per line).
2. Add your proxies to `proxies.txt` (one per line, optional).
3. Run the script:
    ```bash
    bash runscript.sh
    ```
## Note

You can create multiple accounts on the fly by running:
1.  ```bash
    python create_accounts.py
    ``` 
    to generate accounts.

2.  ```bash
    python verify_registrations.py
    ```
    to register generated accounts.

Edit the variable `number_of_key` in `create_accounts.py` to set number of accounts to create


## File Descriptions

- `main.py`: Core script for managing LayerEdge nodes.
- `create_accounts.py`: Generates Ethereum private keys.
- `verify_registrations.py`: Verifies wallet registrations.
- `install.py`: Installs required Python packages.
- `runscript.sh`: Bash script to set up and run the application.
- `requirements.txt`: Lists Python dependencies.
- `.gitignore`: Specifies files and directories to ignore in Git.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Disclaimer

This script is provided as-is without any guarantees. Use it at your own risk.