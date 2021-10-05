from forgot_again.file import load_ast_if_exists


class SecondaryParams:
    def __init__(self, required):
        self._required = required
        self._params = None

    @property
    def params(self):
        if self._params is None:
            self._params = {
                k: v[1]['value'] for k, v in self._required.items()
            }
        return self._params

    @params.setter
    def params(self, d):
        self._params = d

    @property
    def required(self):
        return dict(**self._required)

    def load_from_config(self, file):
        self.params = load_ast_if_exists(file, default=self.params)
