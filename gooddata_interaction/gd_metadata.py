# Class for GoodData interaction
# For test run as a separate file

from gooddata_pandas import GoodPandas
from gooddata_sdk import GoodDataSdk


class GdDt:
    def __init__(self) -> None:
        self._sdk = None
        self._gp = None
        self.wks = {
            'list': [],
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

    def activate(self, host: str, token: str) -> None:
        self._sdk = GoodDataSdk.create(host, token)
        self._gp = GoodPandas(host, token)
        self.wks['list'] = self.get_object()
        # return self  # TODO: need to be here really?

    def identify(self, title: str = '', id: str = '', entity: str = 'workspace') -> str:
        # get **type id/name** submitting name/id
        if entity == 'workspace':
            for w in self.wks['list']:
                if w.name == title or w.id == id:
                    return w.id if title else w.name
        elif entity == 'insight':
            for i in self.wks['insight']:
                if i.title == title or i.id == id:
                    return i.id if title else i.title
        elif entity in ['metric', 'attribute', 'fact']:
            return ''  # TODO: not for now
        else:
            return ''  # empty string for not recognized types

    def list(self, entity: str = 'workspace') -> list:
        if not self._sdk:
            return []
        if entity == 'workspace':
            return [w.name for w in self.get_object()]
        elif entity == 'insight':
            return [i.title for i in self.wks['insight']]
        elif entity == 'metric':
            return [m.obj_id for m in self.wks['metrics']]
        elif entity == 'fact':
            return [f for f in self.wks['facts']]
        elif entity == 'attr':
            return [a for a in self.wks['attrs']]
        elif entity == 'series':
            return list(self.get_object('visual').side_loads._objects.keys())
        else:
            return []

    def select(self, id: str = '', type: str = 'id', entity: str = 'workspace') -> None:
        # select **workspace/dataset/metric**
        if type != 'id':
            id = self.identify(title=id, entity=entity)
        if entity == 'workspace':
            self.active['wks'] = id
            self.wks['catalog'] = self.get_object('catalog')
            self.wks['insight'] = self.get_object('insights')
            self.wks['attrs'] = self.get_object('attrs')
            self.wks['facts'] = self.get_object('facts')
            self.wks['metrics'] = self.get_object('metric')
        elif entity == 'insight':
            self.active['ins'] = id
        elif entity == 'series':
            self.active['dts'] = self.get_object(
                'frames')  # alternatively use series

    def get_object(self, type: str = '') -> any:
        if type == 'catalog':
            return self._sdk.catalog_workspace_content.get_full_catalog(self.active['wks'])
        elif type == 'attrs':
            for a in self.wks['catalog'].datasets:
                for i in range(len(a.attributes)-1):
                    self.wks['attrs'][str(
                        a.attributes[i].obj_id)] = a.attributes[i]
            return self.wks['attrs']
        elif type == 'facts':
            for a in self.wks['catalog'].datasets:
                for i in range(len(a.facts)-1):
                    self.wks['facts'][str(a.facts[i].obj_id)] = a.facts[i]
            return self.wks['facts']
        elif type == 'insights':
            return self._sdk.insights.get_insights(self.active['wks'])
        elif type == 'metric':
            return self._sdk.catalog_workspace_content.get_metrics_catalog(self.active['wks'])
            # return self._sdk.catalog_workspace_content.get_full_catalog(self.active['wks']).metrics
        elif type == 'full':
            return self._sdk.catalog_workspace_content.get_full_catalog(self.active['wks'])
        elif type == 'df':
            return self._gp.data_frames(self.active['wks']).for_insight(self.active['ins'])
        elif type == 'frames':
            return self._gp.data_frames(self.active['wks'])
        elif type == 'series':
            return self._gp.series(self.active['wks'])
        elif type == 'visual':
            return self._sdk.insights.get_insight(self.active['wks'], self.active['ins'])
        else:
            return self._sdk.catalog_workspace.list_workspaces()


if __name__ == "__main__":
    gd = GdDt()
    endpoint = input("Input your endpoint address (http://locahost:3000):")
    token = input("Input your personal access token:")
    gd.activate(endpoint, token)
    print(dir(gd))
