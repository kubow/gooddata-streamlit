# Class for GoodData interaction
# For test run as separate file

from gooddata_pandas import GoodPandas
from gooddata_sdk import GoodDataSdk


class GdDt:
    def __init__(self, host: str = '', token: str = '') -> None:
        self._sdk = None
        self._gp = None
        self._wks = {
            'list': None,
            'catalog': None,
            'insight': None,
            'attrs': {},
            'facts': {},
            'metrics': None,
            'series': None
        }
        self.active = {
            'wks': str,   # workspace
            'ins': str,   # insight
            'dts': str,   # dataset
        }

    def activate(self, host: str, token: str) -> object:
        self._sdk = GoodDataSdk.create(host, token)
        self._gp = GoodPandas(host, token)
        self._wks['list'] = self.get_content()
        return self

    def get_ws(self, ws_name: str = '', ws_id: str = '') -> str:
        # get **workspace id/name** by submit name/id
        for w in self._wks['list']:
            if w.name == ws_name or w.id == ws_id:
                return w.id if ws_name else w.name

    def get_content(self, type: str = '') -> any:
        if type == 'catalog':
            return self._sdk.catalog_workspace_content.get_full_catalog(self.active['wks'])
        elif type == 'attrs':
            for a in self._wks['catalog'].datasets:
                for i in range(len(a.attributes)-1):
                    self._wks['attrs'][str(
                        a.attributes[i].obj_id)] = a.attributes[i]
            return self._wks['attrs']
        elif type == 'facts':
            for a in self._wks['catalog'].datasets:
                for i in range(len(a.facts)-1):
                    self._wks['facts'][str(a.facts[i].obj_id)] = a.facts[i]
            return self._wks['facts']
        elif type == 'insight':
            return self._sdk.insights.get_insights(self.active['wks'])
        elif type == 'metric':
            return self._sdk.catalog_workspace_content.get_metrics_catalog(self.active['wks'])
            # return self._sdk.catalog_workspace_content.get_full_catalog(self.active['wks']).metrics
        elif type == 'full':
            return self._sdk.catalog_workspace_content.get_full_catalog(self.active['wks'])
        elif type == 'frames':
            return self._gp.data_frames(self.active['wks'])
        elif type == 'series':
            return self._gp.series(self.active['wks'])
        elif type == 'visual':
            return self._sdk.insights.get_insight(self.active['wks'], self.active['ins'])
        else:
            return self._sdk.catalog_workspace.list_workspaces()

    def set_ws(self, ws: str = '', type: str = 'id') -> None:
        # select **workspace/dataset/metric**
        if type != 'id':
            ws = self.get_ws(ws_name=ws)
        if ws:
            self.active['wks'] = ws
            self._wks['catalog'] = self.get_content('catalog')
            self._wks['insight'] = self.get_content('insight')
            self._wks['metrics'] = self.get_content('metric')
            self._wks['attrs'] = self.get_content('attrs')


if __name__ == "__main__":
    gd = GdDt()
    gd.activate('https://jav.demo.cloud.gooddata.com',
                'SmFrdWIuVmFqZGE6anVweXRlcjpuK0ttaFh5OXkreTN2SGxBOEhqSVlmVXIrcmx1UnBKMw==')
    print(dir(gd))
