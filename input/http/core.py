import requests

from HIF.exceptions import HIFHttpError40X, HIFHttpError50X, HIFImproperUsage
from HIF.models.storage import TextStorage
from HIF.helpers.mixins import JsonDataMixin


class HttpLink(TextStorage):
    """
    This class is responsible for fetching an external resource over HTTP
    And make the data available through the body and head property.
    It uses TextStorage to save data to a generic location if needed.

    This class provides only one truly public method namely get()
    Classes can use this class to fetch the data from indicated source.
    This class provides a lot of methods that can be overriden
    All these methods tweak the way that the class will connect to the external resource
    A list of all methods intended to be overriden:
    - prepare_link
    - enable_auth
    - send_request
    - store_response
    - handle_error
    This base class
    """

    # HIF interface attributes
    HIF_parameters = {}
    HIF_link = ''

    # Class attributes
    request_headers = {}

    #######################################################
    # BASIC (DJANGO) FUNCTIONALITY
    #######################################################
    # Init methods and other basics

    def __init__(self, *args, **kwargs):
        """
        This functions sets some properties that are not intended for direct use
        or that allow for configuration
        Sometimes you want control about public methods based on context and here defaults are set.
        """
        super(HttpLink, self).__init__(*args, **kwargs)
        self.refresh = False  # on second call we'll return results of first call
        self.session = None  # an optional requests session object to be used
        self._link = ''

    class Meta:
        proxy = True

    #######################################################
    # PUBLIC PROPERTIES
    #######################################################
    # Properties that are intended for other classes
    # and used internally as well

    @property
    def success(self):
        """
        Returns True if status is within HTTP success range
        """
        return bool(self.status >= 200 and self.status < 300)

    @property
    def url(self):
        """
        When asked for the URL and the cached _link is not there,
        this getter will create the correct URL out of self.HIF_link by calling prepare_link
        After that prepare_params and enable_auth are called who can add parameters to the link.
        """
        if not self._link:
            self._link = self.prepare_link()  # sets self._link
            params = [params for params in [self.prepare_params(), self.enable_auth()] if params]
            if params:
                self._link += u'?' + u'&'.join(params)
        return self._link
    @url.setter
    def url(self, value):
        """
        When somebody sets this property. It is presumed you have special reasons to over ride standard behavior,
        in your context.
        If you do not know what you're doing please set self.HIF_link on class level and over ride prepare_link,
        prepare_params or prepare_auth.
        """
        self._link = value

    #######################################################
    # PUBLIC METHODS
    #######################################################
    # These methods are for use by other classes
    # They act upon the external resource

    def get(self, *args, **kwargs):
        """
        Main function.
        Does a get to computed link
        """

        self.setup(*args, **kwargs)

        # Early exit if response is already there and status within success range.
        if self.success and not self.refresh:
            return self
        else:
            self.head = {}
            self.body = ""
            self.status = 0

        # Make request and do basic response handling
        self.send_request()
        self.store_response()
        self.handle_error()

        return self

    #######################################################
    # URL METHODS
    #######################################################
    # These methods together construct the URL that will be used.
    # They are the most important functions to override and change behavior
    # on a link to link basis

    def prepare_link(self):
        """
        Returns what the link is that this class should use.
        By default that is the HIF_link attribute, but some cases may need some processing (like Wiki).
        """
        return unicode(self.HIF_link)

    def prepare_params(self):
        """
        Turns HIF_parameters dictionary into valid query string
        Will execute any callables in values of HIF_parameters
        Returns parameters as an unicode
        """
        params = u''
        if self.HIF_parameters:
            for key ,value in self.HIF_parameters.iteritems():
                if callable(value):
                    value = value()
                params += key + u'=' + unicode(value) + u'&'

            params = params[:-1] # strips '&' from the end
        return params

    def enable_auth(self):
        """
        When authentication is needed,
        this function should set class properties and/or return GET params that provide authentication
        By default there is no authentication.
        """
        return u''

    #######################################################
    # OTHER PROTECTED METHODS
    #######################################################
    # It will be less common to override these methods.
    # They change the behaviour of the public interface on a level,
    # that you probably want the same for every link in the system

    def send_request(self):
        """
        Does a get on the computed link
        Will set storage fields to returned values
        """
        if self.session is None:
            connection = requests
        else:
            connection = self.session
        response = connection.get(self.url, headers=self.request_headers)

        self.head = dict(response.headers)
        self.body = response.content
        self.status = response.status_code

    def store_response(self):
        """
        Stores self if an error occurred (for debug purposes)
        """
        if not self.success:
            self.save()
            return True
        return False

    def handle_error(self):
        """
        Raises exceptions upon error statuses
        """
        if self.status >= 500:
            message = "{} > {} \n\n {}".format(self.type, self.status, self.body)
            raise HIFHttpError50X(message)
        elif self.status >= 400:
            message = "{} > {} \n\n {}".format(self.type, self.status, self.body)
            raise HIFHttpError40X(message)
        else:
            return True


class HttpQueryLink(HttpLink):
    """
    Makes the link class suitable for having a single input.
    This input will be considered the query for the resource.
    Queries will get included through the GET parameters
    """

    HIF_query_parameter = ''

    def get(self, *args, **kwargs):
        """
        The get method does some checks on the arguments
        After that it fills HIF_parameters with the first argument
        Setting the key to HIF_query_parameter which will differ from link to link
        """
        if not len(args) == 1:
            raise HIFImproperUsage(
                "QueryLinks should receive one input through args parameter it received {}.".format(len(args))
            )
        self.HIF_parameters[self.HIF_query_parameter] = args[0]
        super(HttpQueryLink, self).get(*args, **kwargs)

    class Meta:
        proxy = True


class JsonQueryLink(HttpQueryLink, JsonDataMixin):
    """
    This class is the same as HttpQueryLink with some additional functionality to process JSON data.
    """

    request_headers = {
        "Content-Type": "application/json; charset=utf-8"
    }

    def __init__(self, *args, **kwargs):
        super(JsonQueryLink, self).__init__(*args, **kwargs)
        JsonDataMixin.__init__(self)

    @property
    def data_source(self):
        """
        This property should return the data that DataMixin's extract should work with
        """
        return self.body

    class Meta:
        proxy = True