import { useEffect, useRef } from "react";
import {
  Cartesian2,
  Cartesian3,
  ClockRange,
  Color,
  EllipsoidTerrainProvider,
  JulianDate,
  LabelStyle,
  SampledPositionProperty,
  Viewer,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

import type { MapScene } from "../api";

type Props = { scene?: MapScene };

const TRACK_COLORS = [Color.CYAN, Color.LIME, Color.ORANGE];

export function SpaceGlobe({ scene }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);

  useEffect(() => {
    if (!containerRef.current || viewerRef.current) return;

    const viewer = new Viewer(containerRef.current, {
      animation: true,
      timeline: true,
      baseLayer: false,
      terrainProvider: new EllipsoidTerrainProvider(),
      geocoder: false,
      homeButton: true,
      sceneModePicker: false,
      navigationHelpButton: false,
      infoBox: false,
      selectionIndicator: false,
      shouldAnimate: true,
    });
    viewer.scene.globe.baseColor = Color.fromCssColorString("#07111f");
    viewer.scene.backgroundColor = Color.fromCssColorString("#020711");
    viewerRef.current = viewer;

    return () => {
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !scene?.tracks.length) return;

    viewer.entities.removeAll();
    let globalStart: JulianDate | undefined;
    let globalStop: JulianDate | undefined;

    scene.tracks.forEach((track, index) => {
      const position = new SampledPositionProperty();
      for (const sample of track.samples) {
        const time = JulianDate.fromIso8601(sample.timestamp);
        const cartesian = Cartesian3.fromDegrees(
          sample.longitude_deg,
          sample.latitude_deg,
          sample.altitude_m,
        );
        position.addSample(time, cartesian);
        if (!globalStart || JulianDate.lessThan(time, globalStart)) globalStart = time;
        if (!globalStop || JulianDate.greaterThan(time, globalStop)) globalStop = time;
      }

      const color = TRACK_COLORS[index % TRACK_COLORS.length];
      viewer.entities.add({
        id: track.satellite_id,
        name: track.name,
        position,
        point: {
          pixelSize: 9,
          color,
          outlineColor: Color.WHITE,
          outlineWidth: 1,
        },
        label: {
          text: track.name,
          font: "12px sans-serif",
          fillColor: Color.WHITE,
          outlineColor: Color.BLACK,
          outlineWidth: 2,
          style: LabelStyle.FILL_AND_OUTLINE,
          pixelOffset: new Cartesian2(12, -12),
        },
        path: {
          show: true,
          leadTime: 45 * 60,
          trailTime: 45 * 60,
          width: 2,
          material: color.withAlpha(0.75),
        },
      });
    });

    if (globalStart && globalStop) {
      viewer.clock.startTime = globalStart.clone();
      viewer.clock.stopTime = globalStop.clone();
      viewer.clock.currentTime = globalStart.clone();
      viewer.clock.clockRange = ClockRange.LOOP_STOP;
      viewer.clock.multiplier = 120;
      viewer.timeline.zoomTo(globalStart, globalStop);
    }
    viewer.camera.flyHome(0.4);
  }, [scene]);

  return <div className="space-globe" ref={containerRef} />;
}
