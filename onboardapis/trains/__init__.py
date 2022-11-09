"""
Abstract base classes for trains
"""
from __future__ import annotations

import datetime
import time
from typing import Any, Callable, Iterable, TypeVar
from abc import ABCMeta, abstractmethod

from .. import Vehicle, IncompleteVehicleMixin
from ..exceptions import DataInvalidError, NotImplementedInAPIError
from ..utils.conversions import coordinates_to_distance
from ..utils.data import ScheduledEvent, Position


class Station(object):
    """
    A Station is a stop on the trip
    """

    __slots__ = ["_id", "_name", "_platform", "_arrival", "_departure", "_position", "_distance", "_connections"]

    def __init__(self, station_id: Any, name: str, platform: ScheduledEvent[str] = None,
                 arrival: ScheduledEvent[datetime.datetime] = None, departure: ScheduledEvent[datetime.datetime] = None,
                 position: Position = None, distance: float = None, connections: list["ConnectingTrain"] = None):
        """
        Initialize a new :class:`Station`

        :param station_id: The ID of the station
        :type station_id: Any
        :param name: The name of the station
        :type name: str
        :param platform: The platform that the vehicle is arriving at
        :type platform: ScheduledEvent[str]
        :param arrival: The arrival time at this station
        :type arrival: ScheduledEvent[datetime.datetime]
        :param departure: The departure time from this station
        :type departure: ScheduledEvent[datetime.datetime]
        :param position: The geographic position of the station
        :type position: Position
        :param distance: The distance from the start to this station
        :type distance: float
        :param connections: The connecting services departing from this station
        :type connections: Iterable[ConnectingTrain]
        """
        self._id = station_id
        self._name = name
        self._platform = platform
        self._arrival = arrival
        self._departure = departure
        self._position = position
        self._distance = distance
        self._connections = connections

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}>"

    @property
    def id(self) -> Any:
        """
        The unique ID of the station

        :return: The ID of the station
        :rtype: Any
        """
        return self._id

    @property
    def name(self) -> str:
        """
        The name of the station

        :return: The name of the station
        :rtype: str
        """
        return self._name

    @property
    def platform(self) -> ScheduledEvent[str]:
        """
        The platform that the train is arriving at

        :return: The platform
        :rtype: ScheduledEvent[str]
        """
        return self._platform

    @property
    def arrival(self) -> ScheduledEvent[datetime.datetime]:
        """
        The arrival time at this station

        :return: The datetime object of the arrival time encased in a ScheduledEvent
        :rtype: ScheduledEvent[datetime.datetime]
        """
        return self._arrival

    @property
    def departure(self) -> ScheduledEvent[datetime.datetime]:
        """
        The departure time at this station

        :return: The datetime object of the departure time encased in a ScheduledEvent
        :rtype: ScheduledEvent[datetime.datetime]
        """
        return self._departure

    @property
    def connections(self) -> list[ConnectingTrain]:
        """
        The connecting services departing from this station

        :return: A list of ConnectingTrain objects
        :rtype: list[ConnectingTrain]
        """
        return self._connections

    @property
    def distance(self) -> float:
        """
        The distance from the start to this station in meters

        :return: The distance
        :rtype: float
        """
        return self._distance

    @property
    def position(self) -> Position:
        """
        The geographic position of the station

        :return: The coordinates of the station
        :rtype: Position
        """
        return self._position

    def calculate_distance(self, other: Station | tuple[float, float] | int | float) -> float | None:
        """
        Calculate the distance in meters between this station and something else
        Accepts a :class:`Station`, a tuple of (latitude, longitude) or an integer for the distance calculation

        :param other: The other station or position to calculate the distance to
        :type other: Union[Station, Tuple[float, float], int, float]
        :return: The distance in meters
        :rtype: Optional[float]
        """
        # Get the position of the other station or the distance of the other station from the start
        if isinstance(other, Station):
            other = (
                other.distance
                if other.distance is not None
                else (
                    other.position
                    if other.position is not None
                    else None
                )
            )
        # If there is not enough information to calculate the distance, return None
        if other is None:
            return None

        # Calculate the distance
        if isinstance(other, int) or isinstance(other, float):
            return self.distance - other if self.distance - other >= 0 else other - self.distance
        if isinstance(other, tuple):
            return coordinates_to_distance((self.position.latitude, self.position.longitude), other)
        return None


class _LazyStation(Station):
    """
    The LazyStation is a Station that maybe does not yet have information on connecting trains.
    If it does not have information by the time it is requested by the user,
    it will then proceed to load the information through ``lazy_func(self.id)``.
    """

    __slots__ = ["_lazy_func", "_cache_valid_until", "_cache_timeout"]

    def __init__(self, *args, lazy_func: Callable[..., list[ConnectingTrain] | None] = None,
                 _cache_timeout: int = 60, **kwargs):
        super().__init__(*args, **kwargs)
        self._lazy_func = lazy_func
        self._cache_valid_until = 0
        self._cache_timeout = _cache_timeout

    @property
    def connections(self) -> list[ConnectingTrain] | None:
        """
        The connecting services departing from this station

        :return: A list of ConnectingTrain objects
        :rtype: List[ConnectingTrain]
        """
        def request_data() -> list[ConnectingTrain]:
            """
            Perform the request to get the data and return the response
            """
            connections = self._lazy_func(self.id)
            self._connections = connections
            self._cache_valid_until = time.time() + self._cache_timeout  # Cache this result for the next minute
            return connections

        if self._lazy_func is None:
            return self._connections  # None or connections

        # Lazy func is not None
        # Connections may be None or not
        if time.time() > self._cache_valid_until:
            return request_data()
        # Cache time is valid
        # If there is no cache yet, request the data
        if self._connections is None:
            return request_data()
        # Return cached connections
        return self._connections


ID = TypeVar('ID', str, int)
"""
A TypeVar indicating the return type of Train.id and the key type of Train.stations
"""


class Train(Vehicle, metaclass=ABCMeta):
    """
    Interface specifying the attributes of a train
    """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.id}>"

    def now(self) -> datetime.datetime:
        """
        Get the current time from the train

        :return: The current time
        :rtype: datetime.datetime
        """
        return datetime.datetime.now()

    def calculate_distance(self, station: Station) -> float:
        """
        Calculate the distance in meters between the train and a station

        :param station: The station to calculate the distance to
        :type station: Station
        :return: The distance in meters
        :rtype: float
        """
        return station.calculate_distance(self.distance or self.position)

    @property
    @abstractmethod
    def id(self) -> ID:
        """
        The unique ID of this specific train

        :return: The ID
        :rtype: str
        """
        pass

    @property
    @abstractmethod
    def type(self) -> str:
        """
        The abbreviated train type

        :return: The train type
        :rtype: str
        """
        pass

    @property
    @abstractmethod
    def number(self) -> str:
        """
        The line number of this train

        :return: The line number
        :rtype: str
        """
        pass

    @property
    @abstractmethod
    def stations(self) -> dict[ID, Station]:
        """
        The stations that this train passes through returned as a dict with the station ID as the key.
        Mostly ID will be of type str.

        :return: The stations
        :rtype: Dict[str, Station]
        """
        pass

    @property
    @abstractmethod
    def origin(self) -> Station:
        """
        The station where this train started the current journey

        :return: The first station on this trip
        :rtype: Station
        """
        stations = list(self.stations.values())
        if len(stations) > 0:
            return stations[0]
        raise DataInvalidError("No origin station found")

    @property
    @abstractmethod
    def current_station(self) -> Station:
        """
        The station where this train will arrive next or is currently at

        :return: The current station
        :rtype: Station
        """
        # Get the current station id
        # Get the station from the stations dict
        pass

    @property
    @abstractmethod
    def destination(self) -> Station:
        """
        The station where this train will end the current journey

        :return: The last station on this trip
        :rtype: Station
        """
        stations = list(self.stations.values())
        if len(stations) > 0:
            return stations[-1]
        raise DataInvalidError("No destination station found")

    @property
    @abstractmethod
    def speed(self) -> float:
        """
        The current speed of the train in meters / second

        :return: The speed of the train
        :rtype: float
        """
        pass

    @property
    @abstractmethod
    def distance(self) -> float:
        """
        The distance from the start in meters

        :return: The distance
        :rtype: float
        """
        pass

    @property
    @abstractmethod
    def position(self) -> Position:
        """
        The current position of the train as a :class:`Position`

        :return: The position of the train
        :rtype: Position
        """
        pass

    @property
    @abstractmethod
    def delay(self) -> float:
        """
        The current delay of the train in seconds

        :return: The delay of the train
        :rtype: float
        """
        return (self.current_station.arrival.actual - self.current_station.arrival.scheduled).total_seconds()


class ConnectingTrain(object):
    """
    A connecting train is a train that is not part of the main trip but of a connecting service

    It may only have limited information available
    """

    __slots__ = ["train_type", "line_number", "platform", "destination", "departure"]

    def __init__(self, train_type: str | None = None, line_number: str | None = None,
                 platform: ScheduledEvent[str] | None = None, destination: str | None = None,
                 departure: ScheduledEvent[datetime.datetime] | None = None):
        self.train_type: str | None = train_type
        """
        The abbreviated train type
        """
        self.line_number: str | None = line_number
        """
        The line number of the train
        """
        self.platform: ScheduledEvent[str] | None = platform
        """
        The platform where the train will depart from
        """
        self.departure: ScheduledEvent[datetime.datetime] | None = departure
        """
        The departure time of the train
        """
        self.destination: str | None = destination
        """
        The destination of the train
        """

    def __str__(self):
        return (
            f"{self.train_type}{self.line_number} to {self.destination} "
            f"({self.departure.actual.strftime('%H:%M')}, platform {self.platform.actual})"
        )

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.train_type}{self.line_number} -> {self.destination}>"


class IncompleteTrainMixin(Train, IncompleteVehicleMixin):
    """
    Class that implements all remaining abstract methods.
    Used when the operator does not provide the requested data via the API.
    """

    @property
    def id(self) -> ID:
        raise NotImplementedInAPIError()

    @property
    def type(self) -> str:
        raise NotImplementedInAPIError()

    @property
    def number(self) -> str:
        raise NotImplementedInAPIError()

    @property
    def stations(self) -> dict[ID, Station]:
        raise NotImplementedInAPIError()

    @property
    def origin(self) -> Station:
        raise NotImplementedInAPIError()

    @property
    def current_station(self) -> Station:
        raise NotImplementedInAPIError()

    @property
    def destination(self) -> Station:
        raise NotImplementedInAPIError()

    @property
    def speed(self) -> float:
        raise NotImplementedInAPIError()

    @property
    def distance(self) -> float:
        raise NotImplementedInAPIError()

    @property
    def position(self) -> Position:
        raise NotImplementedInAPIError()

    @property
    def delay(self) -> float:
        raise NotImplementedInAPIError()
