from django.utils.deprecation import MiddlewareMixin

class UserEmailHeaderMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if hasattr(request, "user") and request.user.is_authenticated:
            response["X-User-Email"] = request.user.email
        else:
            response["X-User-Email"] = "anonymous"
        return response
