import click

from house import run_house_search
from us_state_abbrev import us_state_to_abbrev


class CityStateParamType(click.ParamType):
    name = 'citystate'

    def _get_state_abbrev(self, state_str):
        try:
            return us_state_to_abbrev[state_str]
        except KeyError:
            self.fail(f"{state_str} is not a valid state.")

    def convert(self, value, param, ctx):

        # Validate that we have both components
        try:
            city, state = value.replace(' ', '').split(',')
        except ValueError:
            self.fail(f"Location string should be provided as city, state.")

        # Validate that we either have the abbreviation, or we can get it.
        state_abbrev = state if len(state) == 2 else self._get_state_abbrev(state)

        return f'{city}, {state_abbrev}'

CITY_STATE_TYPE = CityStateParamType()


@click.command()
@click.option('-b', '--beds', default=1, help='Number of bedrooms.')
@click.option('-l', '--loc', help='Location of home. Should be in city, state abbreviation format.', type=CITY_STATE_TYPE)
@click.option('-p', '--price', type=float, default=500000)
@click.option('-s', '--id-start', type=int, default=5000)
@click.option('-i', '--increments', type=int, default=1000)
def cli(beds, loc, price, id_start, increments):

    run_house_search(beds, loc, price, id_start, increments)


if __name__ == '__main__':
    cli()
