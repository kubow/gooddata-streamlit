# GoodData Cloud streamlit

A demo application to showcase UI for interacting with [GoodData Cloud / CN instances](https://www.gooddata.com/developers/cloud-native/doc/cloud/deploy-and-install/).

Wrapper layer is using [Python SDK](https://www.gooddata.com/developers/cloud-native/doc/cloud/api-and-sdk/python-sdk/) library.

## Workspace preparation

1. Install requirements with `pip install -r ./requirements.txt` <br/>Alternatively use a pipenv (edit the `./pipfile`) `pipenv sync`
2. (optional) using vscode 
   - prepare run streamlit config `vscode/launch.json` 
3. Fill [endpoint URL](https://www.gooddata.com/developers/cloud-native/doc/cloud/getting-started/get-gooddata/) and [personal access token](https://www.gooddata.com/developers/cloud-native/doc/cloud/getting-started/create-api-token/) to the `.env` file and add it to environment variables `source ./.env` <br/>
   Alternatively a `.gooddatarc` file can be used
4. Run the streamlit app
   - vscode config (usually bound to <kbd>F5</kbd> key)
   - `python -m streamlit app.py`
5. (optional) deploy the app
   - only possible from public github repository (clone or fork if you would like to customize)
   - [take care about secrets](https://docs.streamlit.io/streamlit-community-cloud/get-started/deploy-an-app/connect-to-data-sources/secrets-management)

## TO-DO

- [ ] Add dependabot to the repository
- [ ] Prepare various concepts as git branches
- [ ] Deploy the app
- [ ] 
