from functools import wraps
from pyramid.view import view_config
from mock_model import ModelManager


MODEL_ID_KEY = 'model_id'
MISSING_MODEL_ERROR = 'The model you were working on is no longer available. ' \
                      'We have created a new one for you.'


_running_models = ModelManager()


def json_require_model(f):
    """
    Wrap a JSON view in a precondition that checks if the user has a valid
    `model_id` in his or her session and fails if not.

    If the key is missing or no model is found for that key, return a JSON
    object with an `error` flag  set to true and a `message` field.
    """
    @wraps(f)
    def inner(request, *args, **kwargs):
        model_id = request.session.get(MODEL_ID_KEY, None)
        model = _running_models.get(model_id)

        if model is None:
            return {'errorMessage': 'That model is no longer available.'}
        return f(request, model, *args, **kwargs)
    return inner


@view_config(route_name='show_model', renderer='model.mak')
def show_model(request):
    """
    Show the current user's model.

    Get or create an existing `py_gnome.model.Model` using the `model_id`
    field in the user's session.

    If `model_id` was found in the user's session but the model did not exist,
    warn the user and suggest that they reload from a save file.
    """
    model_id = request.session.get(MODEL_ID_KEY, None)
    model, created = _running_models.get_or_create(model_id)
    data = {}

    if created:
        request.session[MODEL_ID_KEY] = model.id

        # A model with ID `model_id` did not exist, so we created a new one.
        if model_id:
            data['warning'] = MISSING_MODEL_ERROR

    data['model'] = model

    return data


@view_config(route_name='run_model', renderer='gnome_json')
@json_require_model
def run_model(request, model):
    """
    Run the user's current model and return a JSON object containing the result
    of the run.
    """
    return {
        'result': model.run()
    }


@view_config(route_name='add_wind_mover', renderer='gnome_json')
@json_require_model
def add_wind_mover(request, model):
    pass
