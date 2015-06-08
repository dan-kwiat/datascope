from __future__ import unicode_literals, absolute_import, print_function, division
import six

from copy import copy

from datascope.configuration import DEFAULT_CONFIGURATION
from core.utils.configuration import ConfigurationProperty
from core.utils.data import reach


class ExtractProcessor(object):

    config = ConfigurationProperty(
        storage_attribute="_config",
        defaults=DEFAULT_CONFIGURATION,
        private=["_objective"],
        namespace="extract_processor"
    )

    def __init__(self, config):
        super(ExtractProcessor, self).__init__()
        assert isinstance(config, dict) and ("_objective" in config or "objective" in config), \
            "ExtractProcessor expects an objective to extract in the configuration."
        self.config = config
        self._at = None
        self._context = {}
        self._objective = {}
        self.load_objective(self.config.objective)

    def load_objective(self, objective):
        assert isinstance(objective, dict), "An objective should be a dict."
        for key, value in six.iteritems(objective):
            if key == "@":
                self._at = value
            elif key.startswith("#"):
                self._context.update({key[1:]: value})
            else:
                self._objective.update({key: value})
        assert self._at, \
            "ExtractProcessor did not load elements to start with from its objective {}. " \
            "Make sure that '@' is specified".format(objective)
        assert self._objective, "No objectives loaded from objective {}".format(objective)

    def extract_from_resource(self, resource):  # TODO: test
        return self.extract(*resource.content)

    def extract(self, content_type, data):
        content_type_method = content_type.replace("/", "_")
        method = getattr(self, content_type_method, None)
        if method is not None:
            return method(data)
        else:
            raise TypeError("Extract processor does not support content_type {}".format(content_type))

    def application_json(self, data):
        context = {}
        for name, objective in six.iteritems(self._context):
            context[name] = reach(objective, data)

        nodes = reach(self._at, data)

        results = []
        for node in nodes:
            result = copy(context)
            for name, objective in six.iteritems(self._objective):
                result[name] = reach(objective, node)
            results.append(result)

        return results

    def text_html(self, soup):  # soup used in eval!

        context = {}
        for name, objective in six.iteritems(self._context):
            context[name] = eval(objective) if objective else objective

        at = elements = eval(self._at)
        if not isinstance(at, list):
            elements = [at]

        results = []
        for el in elements:  # el used in eval!
            result = copy(context)
            for name, objective in six.iteritems(self._objective):
                result[name] = eval(objective) if objective else objective
            results.append(result)

        return results
