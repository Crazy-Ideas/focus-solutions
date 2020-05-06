from flask import flash
from flask_wtf import FlaskForm


class FSForm(FlaskForm):
    def flash_form_errors(self) -> None:
        for _, errors in self.errors.items():
            for error in errors:
                flash(error)
        return


