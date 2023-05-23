# GoodData Cloud streamlit

A demo application to showcase UI for interacting with [GoodData Cloud / CN instances](https://www.gooddata.com/developers/cloud-native/doc/cloud/deploy-and-install/).

## Workspace preparation

1. Install requirements with `pip install -r ./requirements.txt`
   Alternatively use a pipenv (edit the `./pipfile`) `pipenv sync`
2. (optional) if using vscode check `vscode/launch.json` and prepare to run streamlit
3. Fill [endpoint URL](https://www.gooddata.com/developers/cloud-native/doc/cloud/getting-started/get-gooddata/) and [personal access token](https://www.gooddata.com/developers/cloud-native/doc/cloud/getting-started/create-api-token/) to the `.env` file and add it to environment variables `source ./.env`
   Alternatively a `.gooddatarc` file can be used
4. Run the streamlit app
5. (optional) deploy the app
   - [take care about secrets](https://docs.streamlit.io/streamlit-community-cloud/get-started/deploy-an-app/connect-to-data-sources/secrets-management)

## TO-DO

- Add dependabot to the repository
